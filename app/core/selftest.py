"""
app/core/selftest.py
System self-test on boot. Verifies database, storage, config.
"""
import os
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("kukanilea.selftest")

def run_selftest(config: Dict[str, Any]) -> bool:
    logger.info("Running System Self-Test...")
    try:
        # 1. Check Config
        if not config.get("USER_DATA_ROOT"):
            raise ValueError("USER_DATA_ROOT config missing.")
        
        data_root = Path(config["USER_DATA_ROOT"])
        
        # 2. Check Storage Writable
        if not os.access(data_root, os.W_OK):
            raise PermissionError(f"Cannot write to storage: {data_root}")
            
        test_file = data_root / ".selftest_write"
        test_file.write_text("ok")
        test_file.unlink()
        
        # 3. Check DB Reachable
        db_path = config.get("CORE_DB", data_root / "core.sqlite3")
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1").fetchone()
        conn.close()
        
        logger.info("✅ System Self-Test Passed.")
        return True
    except Exception as e:
        logger.critical(f"❌ System Self-Test FAILED: {e}")
        return False
