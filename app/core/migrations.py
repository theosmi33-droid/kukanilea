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
CURRENT_SCHEMA_VERSION = 2

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
        # This is a simple example; actual logic would involve complex syncing
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
            # Base schema initialization
            _set_user_version(conn, 1)
            conn.commit()
            logger.info("Migrated to version 1")
            
        if current_version < 2:
            # Example: Prep for FTS5
            # We trigger the actual build in background
            t = threading.Thread(target=_build_fts_indices, args=(str(db_path),), daemon=True)
            t.start()
            
            _set_user_version(conn, 2)
            conn.commit()
            logger.info("Migrated to version 2 (FTS build triggered)")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()
