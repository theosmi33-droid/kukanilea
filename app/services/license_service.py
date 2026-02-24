"""
app/services/license_service.py
Lokaler Lizenzschlüssel-Service für KUKANILEA.
Validiert Hardware-gebundene Lizenzschlüssel anstelle von Cloud-Abonnements.
"""

import hashlib
import sqlite3
import os
import logging
from datetime import datetime
from app.database import get_db_path

logger = logging.getLogger("kukanilea.license")

class LicenseService:
    def __init__(self):
        self.db_path = get_db_path()

    def _hash_key(self, raw_key: str) -> str:
        # Ein zusätzlicher System-Salt aus der Umgebungsvariable erschwert Rainbow-Table-Angriffe
        salt = os.getenv("KUKA_LICENSE_SALT", "default_salt_if_missing")
        return hashlib.sha256(f"{raw_key}:{salt}".encode()).hexdigest()

    def validate_license(self, raw_key: str) -> bool:
        """Prüft, ob der übergebene Lizenzschlüssel gültig ist."""
        if not raw_key:
            return False

        key_hash = self._hash_key(raw_key)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            cursor = conn.execute(
                "SELECT valid_until, status FROM licenses WHERE key_hash = ? LIMIT 1",
                (key_hash,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Lizenzprüfung fehlgeschlagen: Schlüssel nicht gefunden.")
                return False
                
            if row['status'] != 'active':
                logger.warning(f"Lizenzprüfung fehlgeschlagen: Status ist {row['status']}.")
                return False

            if row['valid_until']:
                valid_until = datetime.fromisoformat(row['valid_until'])
                if valid_until < datetime.utcnow():
                    logger.warning(f"Lizenzprüfung fehlgeschlagen: Lizenz abgelaufen am {valid_until}.")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Datenbankfehler bei Lizenzprüfung: {e}")
            return False
        finally:
            conn.close()

    def register_license(self, raw_key: str, owner: str, valid_until: str = None) -> bool:
        """Registriert einen neuen Lizenzschlüssel im System."""
        key_hash = self._hash_key(raw_key)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO licenses (key_hash, owner, valid_until, status) VALUES (?, ?, ?, 'active')",
                (key_hash, owner, valid_until)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            logger.error("Lizenzschlüssel existiert bereits.")
            return False
        except Exception as e:
            logger.error(f"Fehler bei Lizenz-Registrierung: {e}")
            return False
        finally:
            conn.close()
