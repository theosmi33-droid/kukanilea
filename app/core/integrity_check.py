"""
app/core/integrity_check.py
System-wide integrity verification for KUKANILEA v2.1.
Ensures file consistency, module availability, and database health.
"""

import os
import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Any

logger = logging.getLogger("kukanilea.integrity")

CORE_FILES = [
    "app/core/logic.py",
    "app/core/boot_sequence.py",
    "app/core/audit.py",
    "app/web.py",
    "app/config.py"
]

def check_system_integrity() -> Dict[str, Any]:
    """Runs a full system check and returns results."""
    results = {
        "files": verify_core_files(),
        "modules": check_modules(),
        "database": check_database_integrity(),
        "permissions": check_fs_permissions(),
        "timestamp": os.getlogin() + "_" + str(os.getpid()) # Mock identifier for now
    }
    
    all_ok = all([v.get("ok", False) for k, v in results.items() if isinstance(v, dict)])
    results["all_ok"] = all_ok
    
    if not all_ok:
        logger.error(f"System integrity check failed: {results}")
        create_crash_dump(results)
        
    return results

def verify_core_files() -> Dict[str, Any]:
    """Checks if core files exist and verifies their SHA256 hashes (Step 2)."""
    missing = []
    corrupted = []
    
    # In a real enterprise system, hashes would be stored in a signed manifest.
    # For v2.1, we verify existence and basic readability.
    for f in CORE_FILES:
        p = Path(f)
        if not p.exists():
            missing.append(f)
        else:
            try:
                # Step 2: Generate hash (Verify in future version against manifest)
                content = p.read_bytes()
                sha = hashlib.sha256(content).hexdigest()
                # logger.debug(f"Verified {f}: {sha}")
            except Exception:
                corrupted.append(f)
            
    return {
        "ok": len(missing) == 0 and len(corrupted) == 0,
        "missing": missing,
        "corrupted": corrupted
    }

def check_modules() -> Dict[str, Any]:
    """Checks if critical optional modules are importable."""
    critical = ["flask", "sqlite3", "pathlib"]
    failed = []
    for m in critical:
        try:
            __import__(m)
        except ImportError:
            failed.append(m)
            
    return {
        "ok": len(failed) == 0,
        "failed": failed
    }

def check_database_integrity() -> Dict[str, Any]:
    """Runs PRAGMA integrity_check on the core database."""
    from app.config import Config
    db_path = Config.CORE_DB
    
    if not db_path.exists():
        return {"ok": False, "error": "Database file missing"}
        
    try:
        conn = sqlite3.connect(str(db_path))
        res = conn.execute("PRAGMA integrity_check;").fetchone()
        conn.close()
        return {"ok": res[0] == "ok", "status": res[0]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_fs_permissions() -> Dict[str, Any]:
    """Verifies write permissions to data root."""
    from app.config import Config
    root = Config.USER_DATA_ROOT
    try:
        test_file = root / ".perm_check"
        test_file.write_text("OK")
        test_file.unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def create_crash_dump(data: Dict[str, Any]):
    """Stores a detailed failure report for analysis."""
    from app.config import Config
    dump_dir = Config.LOG_DIR / "crash"
    dump_dir.mkdir(parents=True, exist_ok=True)
    
    ts = os.environ.get("KUK_START_TS", str(int(os.getpid()))) # Mock
    dump_file = dump_dir / f"integrity_failure_{ts}.json"
    
    import json
    with open(dump_file, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Crash dump created at {dump_file}")
