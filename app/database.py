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
        # Attempt to load sqlite-vec if available in the path
        # On many systems it is 'vec0'
        # conn.load_extension("vec0") 
    except Exception:
        pass

    conn.row_factory = sqlite3.Row
    # WAL Mode & Busy Timeout zur Vermeidung von SQLite Locks
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db():
    """Initialisiert die SQLite-Datenbank mit FTS5- und VEC-Unterstützung."""
    db_path = get_db_path()
    os.makedirs(db_path.parent, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # FTS5 for Text Search
    cursor.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search USING fts5(title, content, metadata);"
    )
    cursor.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS article_search USING fts5(article_number, description, unit_price UNINDEXED, content='prices', tokenize='unicode61');"
    )
    
    # Trigger to keep article_search in sync with prices
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prices_ai AFTER INSERT ON prices BEGIN
          INSERT INTO article_search(rowid, article_number, description, unit_price) VALUES (new.id, new.article_number, new.description, new.unit_price);
        END;
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prices_ad AFTER DELETE ON prices BEGIN
          INSERT INTO article_search(article_search, rowid, article_number, description, unit_price) VALUES('delete', old.id, old.article_number, old.description, old.unit_price);
        END;
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS prices_au AFTER UPDATE ON prices BEGIN
          INSERT INTO article_search(article_search, rowid, article_number, description, unit_price) VALUES('delete', old.id, old.article_number, old.description, old.unit_price);
          INSERT INTO article_search(rowid, article_number, description, unit_price) VALUES (new.id, new.article_number, new.description, new.unit_price);
        END;
    """)

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

    # AUTO-REMEDIATION: Performance Indices
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_templates_vertical ON templates(vertical);"
    )

    conn.commit()
    conn.close()
    
    # Initialize SQLAlchemy models
    from app.models.rule import init_sa_db, get_sa_engine
    from app.core.audit_logger import AuditEntry
    from app.services.caldav_sync import CalendarConnection
    try:
        init_sa_db()
        setup_sa_event_listeners(get_sa_engine())
    except Exception as e:
        print(f"SQLAlchemy initialization error: {e}")
        
    print(f"Database initialized at {db_path} with FTS5.")

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
        # Schritt 4: Behandle riskante Operationen
        for obj in session.new | session.dirty | session.deleted:
            action_name = "db_mutation"
            # Versuche Tabellennamen als Action zu nutzen
            table_name = getattr(obj, "__tablename__", "unknown")
            args = {"table": table_name, "data": str(obj)}
            
            # Kritischer Check gegen Observer
            # Schritt 5: Wirft der Observer ein Veto ein, Rollback erzwingen
            allowed, reason = observer.validate_action(action_name, args)
            
            if not allowed:
                # Rollback der Transaktion
                session.rollback()
                # Schritt 6: Protokollierung bereits im Observer._log_veto()
                raise PermissionError(f"Observer Veto: {reason}")


if __name__ == "__main__":
    init_db()
