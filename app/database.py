import os
import sqlite3
from pathlib import Path

DB_PATH = Path("instance/kukanilea.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # AUTO-REMEDIATION: Prevent "database is locked" under load
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db():
    """Initialisiert die SQLite-Datenbank mit FTS5-Unterstützung und Indizes."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # ... (Tabellen-Erstellung bleibt gleich)
    cursor.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search USING fts5(title, content, metadata);"
    )

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
