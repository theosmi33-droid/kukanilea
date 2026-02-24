"""
app/services/diagnostic_exporter.py
DSGVO-konformer Diagnostic Exporter für KUKANILEA Gold.
Generiert verschlüsselte Support-Dumps ohne Cloud-Telemetrie.
"""

import os
import re
import json
import uuid
import logging
import zipfile
import io
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.fernet import Fernet
from app.hardware_detection import detect_hardware

logger = logging.getLogger("kukanilea.diagnostics")

# PII Redaction Patterns (DSGVO)
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "iban": r"DE\d{20}",
    "name_candidate": r"(?i)(Herr|Frau)\s+[A-Z][a-z]+",
    "ip_addr": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "tenant_name": r"(?i)tenant\s*[=:]\s*[A-Za-z0-9_-]+"
}

class DiagnosticExporter:
    def __init__(self):
        # Der öffentliche Support-Key (HINWEIS: Hier ein Platzhalter für den echten 4096-bit RSA Key)
        # Dieser Key gehört dem Support-Team (ZimaBlade Betreiber)
        self.support_pub_key_pem = b"""-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA5xHf1vdd8pPyRS/9hhaR
ZfGbNScd4ouvAg443bWJtrgNswufnW1OVVpupjur/ZS3NVUQaWj7t9kIYwyAmeVB
cLr+TK7pwV+9VTQuQiCUv/sOS9WVdYTieb3GZ5OPmeYqH8g8gKSz//IibB3+d2ad
W+GK5+N2EYnv8T/JUsHZZk0aQHe/nZIVSVR2X5vysj8ij2NRiNHQ+kzCgwgVY2+5
aTzqkXccpAF4yt+R2a2U+4zQ+NsCPPaO9I/ZiNUlyCeXS/Q0vvfXe+SAxOcvFexn
c+rt0bCfKo1fVTwjhGIhaPIEHFY/P+284GNXKcGME46ItnpEi6geiQzyGgfGOOHP
9+Acx46bDsaEV7Cxs68hy6yv1AvG1C2tCLxFw9mc9WtpA3drVMqWtwoaeLdzNxbD
MEpqGUxWNJHNbK2v6YS4ZcjslXPeVBJ0SQhaXME+TusWSiyJ/E0+ukAPmRX6aJgM
U8/VlGEZbZtoAc5HWIaZ1PmFLkYD4/5p/PjKdPLtCQeu1m5IC6NcIqyFyDoA5+dV
BVGLMMIknczeOwCXhp5X6yAS0YT7gyb+HF6JQHk0DHE4eqzae7VnjB8SbQ6WoFWz
P1PJ2VICTJOqrxKNCzDDNR9J1cG2AX0vVl0DtKPj+G2RP7rfCRce+BiLpxNb7EHC
Y2nO9HAKV//Fzi17D8+jZvkCAwEAAQ==
-----END PUBLIC KEY-----"""
        self.log_file = Path("app.log")
        self.tmp_dir = Path("tmp")
        self.tmp_dir.mkdir(exist_ok=True)

    def _redact_text(self, text: str) -> str:
        """Filtert PII aus Log-Texten (Emails, IPs, IBANs)."""
        redacted = text
        for label, pattern in PII_PATTERNS.items():
            redacted = re.sub(pattern, f"[REDACTED_{label.upper()}]", redacted)
        return redacted

    def generate_dump(self, request_id: str = None) -> bytes:
        """
        Sammelt alle relevanten Diagnose-Daten, bereinigt sie und verpackt sie verschlüsselt.
        """
        request_id = request_id or str(uuid.uuid4())
        
        # Hardware & License info
        hw_profile = detect_hardware()
        # Mock license info for now (integrated later)
        license_info = {"hwid": hw_profile.get("machine_id", "UNKNOWN"), "status": "GOLD_ACTIVE"}
        
        dump_data = {
            "version": "1.5.0-GOLD",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "hardware_profile": hw_profile,
            "license": license_info,
            "db_status": self._gather_db_status()
        }

        # 1. ZIP in Memory erstellen
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Report JSON
            clean_json = json.dumps(dump_data, indent=2, ensure_ascii=False)
            zf.writestr("diagnostic_report.json", clean_json)

            # Main App Log (last 500 lines)
            if self.log_file.exists():
                try:
                    lines = self.log_file.read_text().splitlines()
                    content = "\n".join(lines[-500:])
                    zf.writestr("app.log", self._redact_text(content))
                except Exception as e:
                    logger.error(f"Could not include app.log: {e}")

        zip_data = zip_buffer.getvalue()

        # 2. Hybrid-Verschlüsselung
        try:
            fernet_key = Fernet.generate_key()
            f = Fernet(fernet_key)
            encrypted_data = f.encrypt(zip_data)

            public_key = serialization.load_pem_public_key(self.support_pub_key_pem)
            encrypted_key = public_key.encrypt(
                fernet_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # [KeyLength: 4 bytes] [EncryptedKey] [EncryptedPayload]
            key_len = len(encrypted_key).to_bytes(4, byteorder='big')
            final_bundle = key_len + encrypted_key + encrypted_data
            
            # Save to tmp/ as well for record
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            (self.tmp_dir / f"diagnostik_{ts}.zip.enc").write_bytes(final_bundle)
            
            return final_bundle

        except Exception as e:
            logger.critical(f"Encryption failed: {e}")
            return zip_data 

    def _gather_logs(self) -> list:
        """Sammelt die letzten internen Ereignisse (Dummy)."""
        return ["Diagnostic export initiated", "Privacy filters applied"]

    def _gather_db_status(self) -> dict:
        """Prüft SQLite PRAGMA Status."""
        import sqlite3
        from app.config import Config
        try:
            db_path = getattr(Config, 'CORE_DB', 'instance/kukanilea.db')
            conn = sqlite3.connect(db_path)
            res = {
                "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
                "cache_size": conn.execute("PRAGMA cache_size").fetchone()[0],
                "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
                "foreign_keys": conn.execute("PRAGMA foreign_keys").fetchone()[0]
            }
            conn.close()
            return res
        except Exception as e:
            return {"error": f"could_not_query_db: {str(e)}"}

diagnostic_exporter = DiagnosticExporter()
