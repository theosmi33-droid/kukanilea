import os
import sqlite3
import json
from pathlib import Path

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
    # AUTO-REMEDIATION: Prevent "database is locked" under load
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

    # AUTO-REMEDIATION: Performance Indices
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_templates_vertical ON templates(vertical);"
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH} with FTS5.")


if __name__ == "__main__":
    init_db()
