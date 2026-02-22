import logging
import sqlite3

from app.database import get_db_connection

logger = logging.getLogger("kukanilea.maintenance")


def check_integrity():
    """Runs PRAGMA integrity_check on the core database."""
    logger.info("Starting database integrity check.")
    conn = get_db_connection()
    try:
        # SQLite returns multiple rows on failure, exactly one row 'ok' on success.
        cursor = conn.execute("PRAGMA integrity_check;")
        rows = cursor.fetchall()
        
        if len(rows) == 1 and rows[0][0] == "ok":
            logger.info("Database integrity check: PASS")
            return True
        else:
            errors = [r[0] for r in rows]
            logger.error(f"Database integrity check: FAIL - {errors}")
            return False
    except sqlite3.Error:
        logger.exception("Database error during integrity check.")
        return False
    finally:
        conn.close()


def run_vacuum():
    """Defragments the database using VACUUM."""
    logger.info("Starting database VACUUM.")
    conn = get_db_connection()
    try:
        conn.execute("VACUUM;")
        logger.info("Database VACUUM: COMPLETE")
    except sqlite3.Error:
        logger.exception("Database error during VACUUM.")
    finally:
        conn.close()


def apply_performance_settings(conn):
    """Ensures WAL mode and performance pragmas are set."""
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")


def run_maintenance():
    """Full maintenance routine."""
    if not check_integrity():
        # Enter safe mode logic would go here
        logger.critical(
            "SYSTEM ALERT: Database corruption detected. Integrity compromised."
        )
        raise RuntimeError("Database integrity check failed.")

    run_vacuum()


# Stubs to restore import integrity for autonomy module
def get_health_overview():
    return {"status": "ok"}


def record_scan_run(success):
    pass


def rotate_logs():
    pass


def run_backup():
    pass


def run_backup_once(config):
    pass


def run_smoke_test():
    pass


def scan_history_list():
    return []


def verify_backup():
    pass
