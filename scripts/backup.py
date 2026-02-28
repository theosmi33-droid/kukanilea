"""
scripts/backup.py
Automated database backup script.
Run daily via cron/launchctl.
"""
import shutil
import datetime
from pathlib import Path
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger("kukanilea.backup")

def perform_backup():
    # Setup paths
    data_root = Path.home() / "Kukanilea" / "data"
    backup_dir = data_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    databases = [
        "core.sqlite3",
        "auth.sqlite3",
        "audit_vault.sqlite3"
    ]
    
    success = True
    for db_name in databases:
        src = data_root / db_name
        if src.exists():
            dest = backup_dir / f"{db_name}_{timestamp}.bak"
            try:
                shutil.copy2(src, dest)
                logger.info(f"Backed up {db_name} -> {dest.name}")
            except Exception as e:
                logger.error(f"Failed to backup {db_name}: {e}")
                success = False
        else:
            logger.warning(f"Database {db_name} not found at {src}")
            
    # Cleanup old backups (keep last 7 days)
    # Simple logic: keep latest 21 files (7 days * 3 DBs roughly)
    all_backups = sorted(backup_dir.glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(all_backups) > 21:
        for old_backup in all_backups[21:]:
            try:
                old_backup.unlink()
                logger.info(f"Cleaned up old backup: {old_backup.name}")
            except Exception as e:
                logger.error(f"Failed to clean up {old_backup.name}: {e}")

    if success:
        logger.info("Backup routine completed successfully.")
        sys.exit(0)
    else:
        logger.error("Backup routine completed with errors.")
        sys.exit(1)

if __name__ == "__main__":
    perform_backup()
