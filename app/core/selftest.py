"""
app/core/selftest.py
System self-test on boot. Verifies database, storage, config, and capabilities.
"""
import os
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("kukanilea.selftest")

def run_selftest(config: Dict[str, Any]) -> bool:
    logger.info("Running System Self-Test (Production Certification v1.3)...")
    try:
        # 1. Check Config
        if not config.get("USER_DATA_ROOT"):
            raise ValueError("USER_DATA_ROOT config missing.")
        
        data_root = Path(config["USER_DATA_ROOT"])
        
        # 2. Check Storage Writable
        if not data_root.exists():
            data_root.mkdir(parents=True, exist_ok=True)
            
        if not os.access(data_root, os.W_OK):
            raise PermissionError(f"Cannot write to storage: {data_root}")
            
        test_file = data_root / ".selftest_write"
        test_file.write_text("ok")
        test_file.unlink()
        
        # 3. Check DB & FTS5 Capability
        db_path = config.get("CORE_DB", data_root / "core.sqlite3")
        conn = sqlite3.connect(str(db_path))
        
        # Verify FTS5 is compiled in
        fts5_check = conn.execute("SELECT name FROM sqlite_master WHERE name='fts5'").fetchone()
        # Alternatively check via compile options if needed, but checking for a dummy fts5 table creation is better
        try:
            conn.execute("CREATE VIRTUAL TABLE fts_check USING fts5(content)")
            conn.execute("DROP TABLE fts_check")
            logger.info("FTS5 capability verified.")
        except sqlite3.OperationalError:
            logger.warning("FTS5 is NOT available. Search performance will be degraded.")
            
        conn.execute("SELECT 1").fetchone()
        conn.close()
        
        # 4. Check ClamAV (Optional but logged)
        try:
            import pyclamd
            cd = pyclamd.ClamdUnixSocket()
            if cd.ping():
                logger.info("ClamAV Daemon connected.")
            else:
                logger.warning("ClamAV ping failed.")
        except Exception:
            logger.info("ClamAV not reachable (Offline mode or not installed).")
        
        logger.info("✅ System Self-Test Passed.")
        return True
    except Exception as e:
        logger.critical(f"❌ System Self-Test FAILED: {e}")
        return False
