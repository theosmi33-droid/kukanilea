"""
app/core/auth/token_factory.py
Generiert und signiert lokale Identitäts-Tokens (SIT) für das Mesh.
Nutzt Ed25519 für maximale Performance auf Edge-Hardware.
"""

import os
import json
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger("kukanilea.auth.sit")

KEY_PATH = Path("instance/hub_id_key.pem")

class TokenFactory:
    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._load_or_generate_keys()

    def _load_or_generate_keys(self):
        """Lädt den Hub-Schlüssel oder generiert ein neues Paar beim ersten Start."""
        if KEY_PATH.exists():
            try:
                self._private_key = serialization.load_pem_private_key(
                    KEY_PATH.read_bytes(),
                    password=None
                )
                self._public_key = self._private_key.public_key()
                logger.info("Auth: Hub-Schlüsselpaar geladen.")
            except Exception as e:
                logger.error(f"Fehler beim Laden des Schlüssels: {e}")
        
        if not self._private_key:
            logger.info("Auth: Generiere neues Ed25519 Hub-Schlüsselpaar...")
            self._private_key = ed25519.Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
            
            KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEY_PATH.write_bytes(self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption()
            ))

    def get_public_key_hex(self) -> str:
        """Gibt den öffentlichen Schlüssel für das Mesh-Sharing zurück."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

    def create_sit(self, user_uuid: str, username: str, roles: list) -> str:
        """Erstellt ein Signed Identity Token (SIT)."""
        payload = {
            "iss": os.environ.get("INSTANCE_ID", "unknown-hub"),
            "sub": user_uuid,
            "name": username,
            "roles": roles,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        }
        
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = self._private_key.sign(payload_bytes)
        
        token_data = {
            "p": payload,
            "s": signature.hex()
        }
        
        # Base64 Encoding für einfachen Transport im Header
        return base64.b64encode(json.dumps(token_data).encode()).decode()

# Singleton
token_factory = TokenFactory()
