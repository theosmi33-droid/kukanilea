"""
app/core/migrations.py
Database migration system.
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("kukanilea.migrations")

# Current target schema version
CURRENT_SCHEMA_VERSION = 1

def _get_user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]

def _set_user_version(conn: sqlite3.Connection, version: int):
    conn.execute(f"PRAGMA user_version = {version}")

def run_migrations(db_path: Path):
    """Run sequential migrations up to CURRENT_SCHEMA_VERSION."""
    logger.info(f"Checking migrations for {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        current_version = _get_user_version(conn)
        logger.info(f"Current DB version: {current_version}")
        
        if current_version < 1:
            # Base schema initialization logic goes here
            # For now, just bump it to 1
            _set_user_version(conn, 1)
            conn.commit()
            logger.info("Migrated to version 1")
            
        # Add future migrations here:
        # if current_version < 2:
        #     conn.execute("ALTER TABLE...")
        #     _set_user_version(conn, 2)
        #     conn.commit()
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()
