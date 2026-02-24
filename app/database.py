import logging
import time
import os
import sqlite3
import json
from functools import wraps
from pathlib import Path
from sqlalchemy.exc import OperationalError

def retry_on_lock(max_retries: int = 5, delay: float = 0.1):
    """
    Decorator für SQLAlchemy-Operationen, die bei "database is locked" wiederholt werden.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, sqlite3.OperationalError) as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        wait = delay * (2 ** attempt)
                        logging.warning(f"DB Locked, retry {attempt+1}/{max_retries} in {wait}s")
                        time.sleep(wait)
                    else:
                        raise
            raise OperationalError("Max retries for DB Lock exceeded", params=None, orig=None)
        return wrapper
    return decorator

# EPIC 3: Dynamic Database Path Selection
CONFIG_FILE = Path("instance/config.json")
DEFAULT_DB_PATH = Path("instance/kukanilea.db")

def get_db_path() -> Path:
    """Returns the current database path from config or default."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                custom_path = data.get("database_path")
                if custom_path:
                    return Path(custom_path) / "kukanilea.db"
        except Exception:
            pass
    return DEFAULT_DB_PATH

def get_db_connection():
    db_path = get_db_path()
    os.makedirs(db_path.parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    
    # EPIC 3 & 4: Load VEC extension for RAG
    try:
        conn.enable_load_extension(True)
    except Exception:
        pass

    conn.row_factory = sqlite3.Row
    
    # --- PRODUCTION PERFORMANCE HÄRTUNG ---
    # 1. WAL-Mode: Erlaubt parallele Lese- und Schreibzugriffe
    conn.execute("PRAGMA journal_mode=WAL;")
    # 2. Synchronous Normal: Viel schneller auf SSDs, trotzdem sicher im WAL-Mode
    conn.execute("PRAGMA synchronous=NORMAL;")
    # 3. Busy Timeout: Verhindert "Database is locked" bei Lastspitzen
    conn.execute("PRAGMA busy_timeout = 5000;")
    
    # 4. Dynamischer Cache (aus Hardware-Detection)
    cache_mb = os.environ.get("KUKANILEA_ADAPTIVE_DB_CACHE", "128")
    conn.execute(f"PRAGMA cache_size = -{int(cache_mb) * 1024};")
    
    # 5. Memory-Mapped I/O: Lädt Teile der DB direkt in den RAM
    conn.execute("PRAGMA mmap_size = 268435456;") # 256MB
    
    return conn


def init_db():
    """Initialisiert die SQLite-Datenbank mit FTS5- und VEC-Unterstützung."""
    db_path = get_db_path()
    os.makedirs(db_path.parent, exist_ok=True)
    
    # 1. Initialize SQLAlchemy models FIRST
    from app.models.rule import init_sa_db, get_sa_engine
    from app.core.audit_logger import AuditEntry
    from app.services.caldav_sync import CalendarConnection
    from app.models.price import Price, DocumentHash
    try:
        init_sa_db()
        setup_sa_event_listeners(get_sa_engine())
    except Exception as e:
        print(f"SQLAlchemy initialization error: {e}")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 2. FTS5 check and Virtual Table creation
    try:
        cursor.execute("PRAGMA compile_options")
        options = [row[0] for row in cursor.fetchall()]
        fts5_enabled = "ENABLE_FTS5" in options
    except Exception:
        fts5_enabled = False

    if fts5_enabled:
        cursor.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search USING fts5(title, content, metadata);"
        )
    else:
        logging.warning("FTS5 extension missing in SQLite! Falling back to standard tables (slower search).")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_search_fallback (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                metadata TEXT
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fallback_content ON knowledge_search_fallback(content);")

    # article_search relies on 'prices' table
    try:
        if fts5_enabled:
            cursor.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS article_search USING fts5(article_number, description, unit_price UNINDEXED, content='prices', tokenize='unicode61');"
            )
            
            # Trigger to keep article_search in sync with prices
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS prices_ai AFTER INSERT ON prices BEGIN
                  INSERT INTO article_search(rowid, article_number, description, unit_price) VALUES (new.id, new.article_number, new.description, new.unit_price);
                END;
            """)
            # ... and so on
        else:
             cursor.execute("""
                CREATE TABLE IF NOT EXISTS article_search_fallback (
                    rowid INTEGER PRIMARY KEY,
                    article_number TEXT,
                    description TEXT,
                    unit_price REAL
                );
            """)
    except Exception as e:
        print(f"FTS5 Article Search error: {e}")

    # VEC for Semantic Search (RAG)
    # Dimensions: 384 (all-MiniLM-L6-v2)
    try:
        cursor.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(embedding float[384]);"
        )
    except Exception:
        # Fallback if vec0 is not yet installed/loaded
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            type TEXT NOT NULL,
            data_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vertical TEXT NOT NULL,
            name TEXT NOT NULL,
            content_json TEXT NOT NULL
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            action_json TEXT,
            status TEXT DEFAULT 'new',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # --- PRODUCTION READINESS INDICES (Chapter 6) ---
    
    # Ensure core tables exist (minimal schema if not handled by SQLAlchemy)
    cursor.execute("CREATE TABLE IF NOT EXISTS contacts (id TEXT PRIMARY KEY, tenant_id TEXT, customer_id TEXT, name TEXT, email TEXT, created_at TEXT);")
    cursor.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, tenant_id TEXT, column_id TEXT, assigned_to TEXT, status TEXT, created_at TEXT);")
    cursor.execute("CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, tenant_id TEXT, ocr_text TEXT, tags TEXT, created_at TEXT);")

    # 1. Tenant-Isolation
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tenant ON tasks(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);")

    # 2. Primary-Keys + Foreign-Keys
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_column ON tasks(column_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to);")

    # 3. Häufige Filter & Sortierung
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_created ON entities(created_at DESC);")

    # 4. Composite-Indizes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tenant_status_created ON tasks(tenant_id, status, created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_tenant_name ON contacts(tenant_id, name COLLATE NOCASE);")

    # 5. FTS5 Synchronization Trigger
    if fts5_enabled:
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS knowledge_sync_ai AFTER INSERT ON documents
            BEGIN
                INSERT INTO knowledge_search(rowid, title, content) 
                VALUES (new.rowid, new.id, new.ocr_text);
            END;
        """)

    # AUTO-REMEDIATION: Performance Indices
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_templates_vertical ON templates(vertical);"
    )

    conn.commit()
    conn.close()
    
    print(f"Database initialized at {db_path} with FTS5 and WAL.")

def setup_sa_event_listeners(engine):
    """
    Verbindet den Observer mit SQLAlchemy Events (before_commit).
    Prüft riskante Operationen gegen BOUNDARIES.md.
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.agents.observer import ObserverAgent

    @event.listens_for(Session, "before_commit")
    def receive_before_commit(session):
        observer = ObserverAgent()
        
        # Riskante Änderungen identifizieren (Insert, Update, Delete)
        for obj in session.new | session.dirty | session.deleted:
            table_name = getattr(obj, "__tablename__", "unknown")
            
            # Sicherheit: Audit-Logs und GoBD-Hashes sind vom Veto ausgenommen
            if table_name in ["audit_logs", "document_hashes"]:
                continue
                
            action_name = "db_mutation"
            args = {"table": table_name, "data": str(obj)}
            
            # Kritischer Check gegen Observer
            allowed, reason = observer.validate_action(action_name, args)
            
            if not allowed:
                raise PermissionError(f"Observer Veto: {reason}")


if __name__ == "__main__":
    init_db()
