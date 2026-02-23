"""
app/core/privacy_manager.py
DSGVO-konforme Löschroutine für PII und temporäre Dateien.
"""

import os
import glob
import logging
from datetime import datetime, timedelta
from pathlib import Path

from app.models.rule import get_sa_session
from app.core.audit_logger import AuditEntry

logger = logging.getLogger("kukanilea.privacy")

class PrivacyManager:
    def __init__(self, tmp_dir: str = "tmp/"):
        self.tmp_dir = Path(tmp_dir)

    def purge_expired_data(self, retention_days: int = 30):
        """
        Löscht Audit-Logs und temporäre Dateien, die älter als retention_days sind.
        Erfüllt DSGVO Art. 5 (Speicherbegrenzung) und Art. 17 (Recht auf Löschung).
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        logger.info(f"Starte DSGVO-Löschroutine (Cutoff: {cutoff_date})")

        # 1. Temporäre Dateien löschen
        if self.tmp_dir.exists():
            for filepath in self.tmp_dir.glob("*"):
                if filepath.is_file():
                    try:
                        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                        if mtime < cutoff_date:
                            filepath.unlink()
                            logger.debug(f"Gelöscht (DSGVO): {filepath}")
                    except Exception as e:
                        logger.error(f"Fehler beim Löschen von {filepath}: {e}")

        # 2. Alte PII in Agenten-Logs (AuditEntry) löschen oder anonymisieren
        session = get_sa_session()
        try:
            deleted_count = session.query(AuditEntry).filter(AuditEntry.timestamp < cutoff_date).delete()
            session.commit()
            logger.info(f"DSGVO-Löschung: {deleted_count} alte Audit-Einträge entfernt.")
        except Exception as e:
            logger.error(f"Fehler bei DSGVO-Datenbank-Purge: {e}")
            session.rollback()
        finally:
            session.close()

if __name__ == "__main__":
    pm = PrivacyManager()
    pm.purge_expired_data()
