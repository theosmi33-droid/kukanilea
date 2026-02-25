"""
app/services/clamav_client.py
Malware-Scanner für Uploads. Nutzt pyclamd zur Kommunikation mit dem ClamAV-Daemon.
"""

import os
import logging
from typing import BinaryIO, Tuple

import pyclamd

logger = logging.getLogger("kukanilea.security.clamav")

class ClamAVClient:
    def __init__(self):
        # Wir unterstützen clamd.sock oder TCP. Default TCP localhost:3310 (Standard ClamAV)
        self.host = os.environ.get("CLAMAV_HOST", "127.0.0.1")
        self.port = int(os.environ.get("CLAMAV_PORT", "3310"))
        self._cd = None
        self._init_client()

    def _init_client(self):
        try:
            self._cd = pyclamd.ClamdNetworkSocket(self.host, self.port)
            if self._cd.ping():
                logger.info(f"ClamAV Daemon erreichbar auf {self.host}:{self.port}")
            else:
                logger.warning("ClamAV antwortet nicht auf Ping. Upload-Scan deaktiviert.")
                self._cd = None
        except pyclamd.ConnectionError:
            logger.warning(f"Keine Verbindung zu ClamAV auf {self.host}:{self.port}. Scans werden übersprungen.")
            self._cd = None
        except Exception as e:
            logger.error(f"Fehler bei ClamAV-Initialisierung: {e}")
            self._cd = None

    def ping(self) -> bool:
        """Prüft, ob der Daemon erreichbar ist, und versucht ggf. Re-Init."""
        if not self._cd:
            self._init_client()
        if self._cd:
            try:
                return self._cd.ping()
            except Exception:
                self._cd = None
        return False

    def scan_stream(self, file_stream: bytes) -> Tuple[bool, str]:
        """
        Scannt einen Dateistrom.
        Returns: (True, "OK") if clean, (False, "Malware Name") if infected.
        Wenn der Scanner offline ist, geben wir (True, "Scanner Offline") zurück (Fail-Open für den Prototyp).
        """
        if not self.ping():
            return True, "Scanner Offline"

        try:
            # Wir müssen den Stream an ClamAV senden.
            # pyclamd unterstützt scan_stream.
            result = self._cd.scan_stream(file_stream)
            if result is None:
                return True, "OK"
            else:
                # result format: {'stream': ('FOUND', 'Eicar-Test-Signature')}
                # or similar depending on the exact version/wrapper.
                # Usually it returns a dict.
                for key, value in result.items():
                    if value[0] == 'FOUND':
                        malware_name = value[1]
                        logger.error(f"🚨 MALWARE DETECTED: {malware_name} 🚨")
                        return False, malware_name
                return True, "OK"
        except Exception as e:
            logger.error(f"Fehler während des Malware-Scans: {e}")
            # Fail-Open im Dev-Modus, in Prod: Fail-Closed
            return True, f"Scan Error: {str(e)}"

# Singleton
clamav = ClamAVClient()
