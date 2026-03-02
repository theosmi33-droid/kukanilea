"""License signature verification and validity checks."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from nacl.signing import VerifyKey


def verify_signature(pub_hex: str, payload: Dict[str, Any]) -> bool:
    sig_hex = payload.pop("signature", None)
    if not sig_hex:
        return False

    try:
        verify_key = VerifyKey(bytes.fromhex(pub_hex))
        message = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        verify_key.verify(message, bytes.fromhex(sig_hex))
        return True
    except Exception:
        return False


def check_license_file(license_path: str, pub_hex_env: str) -> Dict[str, Any]:
    path = Path(license_path)
    if not path.exists():
        return {"status": "MISSING"}

    payload = json.loads(path.read_text(encoding="utf-8"))
    pub_hex = os.environ.get(pub_hex_env)
    if not pub_hex:
        raise RuntimeError(f"Public key env missing: {pub_hex_env}")

    if not verify_signature(pub_hex, dict(payload)):
        return {"status": "INVALID_SIGNATURE"}

    valid_until = payload.get("valid_until")
    if valid_until:
        expires = datetime.strptime(valid_until, "%Y-%m-%d").replace(tzinfo=timezone.utc).date()
        if expires < datetime.now(timezone.utc).date():
            return {"status": "EXPIRED"}

    return {
        "status": "OK",
        "tenant_id": payload.get("tenant_id"),
        "hw": payload.get("hw_fingerprint"),
    }
