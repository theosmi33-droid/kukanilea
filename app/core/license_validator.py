"""
Lizenzprüfung für KUKANILEA (Zero-Payment-Rule).
Bindet die Lizenz an die lokale Hardware-ID (MAC-Adresse) und verifiziert sie kryptografisch via RSA.
"""
import uuid
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger("kukanilea.license")

class LicenseValidator:
    def __init__(self):
        self.license_path = Path("instance/license.bin")
        # In einer echten Distribution würde dieser Key fest im Binary eingebaut sein
        self.public_key_pem = os.environ.get("KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY", "").encode('utf-8')

    def _get_hardware_id(self) -> str:
        """Ermittelt die eindeutige Hardware-ID des Systems (MAC-basiert)."""
        mac = uuid.getnode()
        # Formatieren als hex-string für Konsistenz
        return f"{mac:012x}"

    def validate(self) -> bool:
        """
        Prüft, ob eine gültige, auf diese Hardware ausgestellte Lizenz existiert.
        Returns: True wenn gültig, False wenn ungültig (System geht in Read-Only).
        """
        from app.config import Config
        if Config.TESTING:
            return True
            
        if not self.license_path.exists():
            logger.warning("Keine Lizenzdatei gefunden (license.bin fehlt). System läuft im Read-Only Modus.")
            return False

        if not self.public_key_pem:
            # Fallback für Entwicklung, wenn kein Key gesetzt ist
            if os.environ.get("KUKANILEA_DEV_MODE") == "1":
                return True
            logger.error("Kein RSA Public Key für die Lizenzprüfung konfiguriert.")
            return False

        try:
            with open(self.license_path, "rb") as f:
                data = f.read()

            # Format: [Signatur (256 Bytes bei RSA-2048)] + [Payload JSON]
            # Wir nehmen der Einfachheit halber an, dass die Signatur durch ein Trennzeichen
            # oder ein festes Format separiert ist. Wir implementieren hier ein einfaches
            # JSON-basiertes Format mit Base64-Signatur.
            
            try:
                license_data = json.loads(data.decode('utf-8'))
                signature = bytes.fromhex(license_data.get('signature', ''))
                payload_str = json.dumps(license_data.get('payload', {}), sort_keys=True)
                payload_bytes = payload_str.encode('utf-8')
            except Exception as e:
                logger.error(f"Lizenzformat ungültig: {e}")
                return False

            public_key = load_pem_public_key(self.public_key_pem)
            
            # Verifiziere die Signatur
            public_key.verify(
                signature,
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # Verifiziere die Hardware-Bindung
            hardware_id = self._get_hardware_id()
            licensed_hw_id = license_data['payload'].get('hardware_id')

            if hardware_id != licensed_hw_id:
                logger.error(f"Lizenzverletzung: Hardware-ID stimmt nicht überein. (Erwartet: {licensed_hw_id}, Aktuell: {hardware_id})")
                return False

            return True

        except InvalidSignature:
            logger.error("Lizenzverletzung: Ungültige RSA-Signatur. Datei manipuliert.")
            return False
        except Exception as e:
            logger.error(f"Unerwarteter Fehler bei der Lizenzprüfung: {e}")
            return False

license_validator = LicenseValidator()
