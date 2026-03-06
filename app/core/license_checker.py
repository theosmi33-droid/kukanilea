"""License signature verification and validity checks."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
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
    try:
        grace_days = int(os.environ.get("LICENSE_GRACE_DAYS", "0"))
    except ValueError:
        grace_days = 0
    now = datetime.now(timezone.utc)

    if not path.exists():
        return {"status": "LOCK", "reason": "MISSING"}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "LOCK", "reason": "INVALID_LICENSE_FILE"}

    if not isinstance(payload, dict):
        return {"status": "LOCK", "reason": "INVALID_LICENSE_PAYLOAD"}

    pub_hex = os.environ.get(pub_hex_env)
    if not pub_hex:
        return {"status": "LOCK", "reason": "MISSING_PUBLIC_KEY"}

    if not verify_signature(pub_hex, dict(payload)):
        return {"status": "LOCK", "reason": "INVALID_SIGNATURE"}

    valid_until = payload.get("valid_until")
    if valid_until:
        try:
            expires = datetime.strptime(valid_until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return {"status": "LOCK", "reason": "INVALID_VALID_UNTIL"}
        if expires < now:
            grace_anchor_raw = payload.get("last_verified_at") or valid_until
            try:
                grace_anchor = datetime.strptime(grace_anchor_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return {"status": "LOCK", "reason": "INVALID_GRACE_ANCHOR"}
            grace_until = grace_anchor + timedelta(days=grace_days)
            if grace_days > 0 and now <= grace_until:
                return {
                    "status": "WARN",
                    "reason": "GRACE",
                    "grace_until": grace_until.date().isoformat(),
                }
            return {"status": "LOCK", "reason": "EXPIRED"}

    return {
        "status": "OK",
        "reason": "VALID",
        "tenant_id": payload.get("tenant_id"),
        "hw": payload.get("hw_fingerprint"),
    }
