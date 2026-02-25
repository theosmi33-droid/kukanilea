"""
app/core/auth/mesh_validator.py
Verifiziert fremde Identitäts-Tokens (SIT) im Mesh.
Führt kryptographische Prüfungen ohne Cloud-Abfrage durch.
"""

import json
import base64
import logging
import sqlite3
from cryptography.hazmat.primitives.asymmetric import ed25519
from app.config import Config

logger = logging.getLogger("kukanilea.auth.validator")

def verify_mesh_token(token_b64: str) -> dict:
    """
    Prüft ein Mesh-Token gegen die lokale mesh_identities Registry.
    Returns: Payload-Dict bei Erfolg, None bei Fehler.
    """
    try:
        raw_json = base64.b64decode(token_b64).decode()
        token_data = json.loads(raw_json)
        payload = token_data.get("p")
        signature = bytes.fromhex(token_data.get("s", ""))
        
        hub_id = payload.get("iss")
        user_uuid = payload.get("sub")
        
        # 1. Öffentlichen Schlüssel des ausstellenden Hubs aus Registry laden
        con = sqlite3.connect(str(Config.CORE_DB))
        con.row_factory = sqlite3.Row
        identity = con.execute(
            "SELECT public_key_hex FROM mesh_identities WHERE user_uuid = ?",
            (user_uuid,)
        ).fetchone()
        con.close()
        
        if not identity:
            logger.warning(f"Validation: Unbekannte Mesh-Identität {user_uuid}")
            return None
            
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(identity["public_key_hex"])
        )
        
        # 2. Signatur verifizieren
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        public_key.verify(signature, payload_bytes)
        
        # 3. Ablaufdatum prüfen
        from datetime import datetime, timezone
        if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            logger.warning("Validation: Mesh-Token abgelaufen.")
            return None
            
        logger.info(f"✅ Mesh-Authentifizierung erfolgreich: {payload.get('name')}")
        return payload
        
    except Exception as e:
        logger.error(f"Fehler bei Mesh-Validierung: {e}")
        return None
