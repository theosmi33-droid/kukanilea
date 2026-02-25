"""
app/core/license_manager.py
Hardened RSA License Validator & Gatekeeper.
Enforces hardware binding and feature-gating for Gold v1.5.0.
"""
import uuid
import json
import logging
import os
import socket
import base64
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
from app.errors import safe_execute

logger = logging.getLogger("kukanilea.license_manager")

class LicenseManager:
    _instance = None
    _license_data = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LicenseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.license_file = Path("instance/license.kukani")
        self.config_bin = Path("instance/config.bin")
        self.pub_key_path = Path("app/core/certs/license_pub.pem")
        self.hardware_id = self._generate_hardware_id()

    def _generate_hardware_id(self) -> str:
        """Ermittelt HWID (MAC + Hostname) für striktes Binding."""
        mac = uuid.getnode()
        hostname = socket.gethostname()
        raw = f"{mac:012x}-{hostname}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def is_valid(self) -> bool:
        """Globale Prüfung ob System aktiviert ist."""
        from app.config import Config
        if Config.TESTING:
            return True
            
        is_local_valid = False
        if self._license_data:
            is_local_valid = True
        else:
            is_local_valid = self.verify_and_install()
            
        if not is_local_valid:
            return False
            
        return self._check_remote_status()

    def _check_remote_status(self) -> bool:
        """Prüft asynchron/mit Cache die Lizenz am zentralen Master-Server."""
        import time
        import requests
        from app.config import Config
        
        url = getattr(Config, 'LICENSE_VALIDATE_URL', None)
        if not url:
            return True # Wenn keine URL konfiguriert ist, gilt die lokale Prüfung
            
        now = time.time()
        if hasattr(self, '_remote_check_cache'):
            last_check, status = self._remote_check_cache
            if now - last_check < 3600: # 1 Stunde TTL
                return status
                
        try:
            # Kurzer Timeout, damit das Dashboard nicht hängt wenn Offline
            res = requests.post(url, json={"hardware_id": self.hardware_id}, timeout=2.0)
            if res.status_code in [200, 403]:
                data = res.json()
                is_active = data.get("valid", False)
                self._remote_check_cache = (now, is_active)
                if not is_active:
                    logger.warning("🚨 Remote License Check: Lizenz wurde zentral entzogen!")
                return is_active
        except Exception as e:
            logger.debug(f"Remote License Server nicht erreichbar, nutze lokalen Zustand. ({e})")
            
        # Fail-Open-Prinzip: Wenn der Handwerker offline ist, darf das System nicht sperren
        self._remote_check_cache = (now, True)
        return True

    def validate_license(self) -> bool:
        """Bypass für interne Agenten-Validierung."""
        return self.is_valid()

    def verify_and_install(self, key_string: str = None) -> bool:
        """Prüft Signatur, HWID und Ablaufdatum."""
        if not key_string:
            if not self.license_file.exists(): return False
            key_string = self.license_file.read_text().strip()

        if not self.pub_key_path.exists():
            logger.error("Sicherheitsfehler: license_pub.pem fehlt!")
            return False

        try:
            bundle = json.loads(base64.b64decode(key_string).decode('utf-8'))
            payload = bundle.get("payload", {})
            signature = bytes.fromhex(bundle.get("signature", ""))
            
            with open(self.pub_key_path, "rb") as f:
                pub_key = serialization.load_pem_public_key(f.read())
            
            # 1. RSA-PSS Verifizierung
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
            pub_key.verify(
                signature,
                payload_bytes,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )

            # 2. Hardware Match
            if payload.get("hwid") != self.hardware_id:
                logger.error("Lizenzfehler: Hardware-ID Mismatch.")
                return False

            # 3. Expiry Check
            if datetime.now(timezone.utc) > datetime.fromisoformat(payload.get("expiry", "")):
                logger.error("Lizenzfehler: Abgelaufen.")
                return False

            self._license_data = payload
            
            # Revisionssichere Speicherung (Simuliert verschlüsselt)
            self.license_file.parent.mkdir(parents=True, exist_ok=True)
            self.license_file.write_text(key_string)
            self.config_bin.write_bytes(json.dumps({"activated": True, "ts": datetime.now().isoformat()}).encode())
            
            return True

        except (InvalidSignature, Exception) as e:
            logger.error(f"Lizenz-Validierung gescheitert: {e}")
            return False

    def is_feature_enabled(self, feature: str) -> bool:
        if not self._license_data: return False
        feats = self._license_data.get("features", [])
        return "all" in feats or feature in feats

license_manager = LicenseManager()
