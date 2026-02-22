import os
import sqlite3
from pathlib import Path

DB_PATH = Path("instance/kukanilea.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialisiert die SQLite-Datenbank mit FTS5-Unterstützung."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Erstelle Tabelle für Dokumente/Wissen mit FTS5
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search 
        USING fts5(title, content, metadata);
    """)

    # Erstelle Basis-Tabellen für CRM und Tasks (Vorbereitung EPIC 2)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            type TEXT NOT NULL,
            data_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # EPIC 6: Branchen-Templates (Vertical Kits)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vertical TEXT NOT NULL,
            name TEXT NOT NULL,
            content_json TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH} with FTS5.")

if __name__ == "__main__":
    init_db()
