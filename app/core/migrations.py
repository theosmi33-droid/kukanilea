"""
app/core/migrations.py
Database migration system. Supports background index building.
"""
import sqlite3
import logging
import threading
from pathlib import Path

logger = logging.getLogger("kukanilea.migrations")

# Current target schema version
CURRENT_SCHEMA_VERSION = 6

def _get_user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]

def _set_user_version(conn: sqlite3.Connection, version: int):
    conn.execute(f"PRAGMA user_version = {version}")

def _build_fts_indices(db_path: str):
    """Worker to build FTS indices in background to avoid blocking boot."""
    logger.info("Starting background FTS index build...")
    conn = sqlite3.connect(db_path)
    try:
        # 1. Create FTS5 virtual table if missing
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(doc_id, content)")
        
        # 2. Sync from main docs table
        conn.execute("""
            INSERT INTO docs_fts(doc_id, content)
            SELECT doc_id, extracted_text FROM docs
            WHERE doc_id NOT IN (SELECT doc_id FROM docs_fts)
        """)
        conn.commit()
        logger.info("✅ Background FTS index build complete.")
    except Exception as e:
        logger.error(f"FTS background build failed: {e}")
    finally:
        conn.close()

def run_migrations(db_path: Path):
    """Run sequential migrations up to CURRENT_SCHEMA_VERSION."""
    logger.info(f"Checking migrations for {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        current_version = _get_user_version(conn)
        logger.info(f"Current DB version: {current_version}")
        
        if current_version < 1:
            _set_user_version(conn, 1)
            conn.commit()
            
        if current_version < 2:
            t = threading.Thread(target=_build_fts_indices, args=(str(db_path),), daemon=True)
            t.start()
            _set_user_version(conn, 2)
            conn.commit()

        if current_version < 3:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  agent_role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  embedding BLOB NOT NULL,
                  metadata TEXT,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_tenant_ts ON agent_memory(tenant_id, timestamp);")
            _set_user_version(conn, 3)
            conn.commit()

        if current_version < 4:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mesh_nodes(
                  node_id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  public_key TEXT NOT NULL,
                  last_ip TEXT,
                  last_seen TEXT,
                  status TEXT DEFAULT 'OFFLINE',
                  trust_level INTEGER DEFAULT 0
                );
                """
            )
            _set_user_version(conn, 4)
            conn.commit()

        if current_version < 5:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_outbound_queue(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  target_system TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  file_path TEXT,
                  status TEXT DEFAULT 'pending',
                  retry_count INTEGER DEFAULT 0,
                  created_at TEXT NOT NULL,
                  last_attempt TEXT,
                  error_message TEXT
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_queue_status ON api_outbound_queue(status);")
            _set_user_version(conn, 5)
            conn.commit()

        if current_version < 6:
            # Task: Memory Intelligence (Importance & Category)
            conn.execute("ALTER TABLE agent_memory ADD COLUMN importance_score INTEGER DEFAULT 5;")
            conn.execute("ALTER TABLE agent_memory ADD COLUMN category TEXT DEFAULT 'FAKT';")
            _set_user_version(conn, 6)
            conn.commit()
            logger.info("Migrated to version 6 (Memory Intelligence)")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()
