from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict

# Backward compatibility: legacy Ed25519 licenses remain supported.
PUBLIC_KEY_HEX = "d9213284c379d7ffd915619a57d2105fa4f39bbf2b25fa39d1d189bd57778b07"

# Primary verifier: RSA-PSS SHA-256.
DEFAULT_RSA_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtJ+EbD8JXXVGvRTyQAB8
ZgWJDIFRsYMbQHx9ckGi8Ur+PakHZZbeqNJIIhhquBv7m5qmbM1NQR4j2fa6Au1o
EuGxaYFo40ehS7baWgp7KLy3nZ5qZK6wjjg2bEIlPz0YaYrCkK4FCTMHkbUUutTs
w36JLy6yYM+2BggnT4GlQHMLxUtqJrRquU7LSCgwYyr1eAax4fN5UR+TpPn439Td
kWXeCvY+VMdFgbGe9n1sDR8KrF5UwRlHC81xUJeZrtdH9YuUyQI7MVI2G7ezCbwF
1AdWfYbWUHg3/p3wm871EIsQjyaBRlFtkULGUZlwsiW9hG//NQUg4LlZHt5XBqmx
EwIDAQAB
-----END PUBLIC KEY-----
"""

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except Exception:  # pragma: no cover - optional at import time
    hashes = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    padding = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore
    InvalidSignature = Exception  # type: ignore[assignment]


@dataclass
class LicenseState:
    plan: str
    trial: bool
    trial_days_left: int
    expired: bool
    device_mismatch: bool
    read_only: bool
    reason: str
    status: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "plan": self.plan,
            "trial": self.trial,
            "trial_days_left": self.trial_days_left,
            "expired": self.expired,
            "device_mismatch": self.device_mismatch,
            "read_only": self.read_only,
            "reason": self.reason,
            "status": self.status,
        }


def _normalize_license_status(value: Any) -> str:
    raw = str(value or "active").strip().lower()
    if raw in {"active", "aktiv"}:
        return "active"
    if raw in {"blocked", "gesperrt", "locked", "suspended"}:
        return "blocked"
    if raw in {"grace", "grace_period", "kulanz"}:
        return "grace"
    return "active"


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _rsa_public_key_pem() -> str:
    value = os.environ.get("KUKANILEA_LICENSE_RSA_PUBLIC_KEY_PEM", "").strip()
    return value or DEFAULT_RSA_PUBLIC_KEY_PEM


def _verify_rsa_signature(payload: Dict[str, Any], signature_b64: str) -> bool:
    if serialization is None or hashes is None or padding is None:
        return False
    try:
        public_key = serialization.load_pem_public_key(
            _rsa_public_key_pem().encode("utf-8")
        )
        signature = base64.b64decode(signature_b64, validate=True)
        public_key.verify(
            signature,
            _canonical_payload_bytes(payload),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        return False


def _verify_ed25519_signature(payload: Dict[str, Any], signature_b64: str) -> bool:
    if Ed25519PublicKey is None:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
        signature = base64.b64decode(signature_b64, validate=True)
        public_key.verify(signature, _canonical_payload_bytes(payload))
        return True
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        return False


def device_fingerprint() -> str:
    """
    Combines machine UUID, CPU info and MAC to create a stable HWID.
    """
    import platform
    import subprocess

    hwid_parts = [str(uuid.getnode())]

    try:
        if platform.system() == "Darwin":
            # Avoid shell=True for security
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            ).decode()
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    hwid_parts.append(line.strip())
                    break
        elif platform.system() == "Windows":
            out = subprocess.check_output(["wmic", "csproduct", "get", "uuid"]).decode()
            hwid_parts.append(out.strip())
    except Exception:
        pass

    raw = "::".join(hwid_parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def get_activation_code() -> str:
    """
    Returns a formatted version of the HWID for the user to copy.
    """
    fp = device_fingerprint()
    return f"KUK-{fp[:4]}-{fp[4:8]}-{fp[8:12]}-{fp[12:16]}"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def load_license(license_path: Path) -> Dict[str, Any]:
    if not license_path.exists():
        return {"valid": False, "reason": "missing"}

    try:
        raw = _load_json(license_path)
        signature_b64 = str(raw.get("signature") or "")
        if not signature_b64:
            return {"valid": False, "reason": "missing_signature"}

        algorithm = str(raw.get("algorithm") or raw.get("alg") or "RSA_PSS_SHA256").upper()

        payload = dict(raw)
        payload.pop("signature", None)
        payload.pop("algorithm", None)
        payload.pop("alg", None)

        if algorithm in {"RSA", "RSA_PSS_SHA256", "RSA-SHA256"}:
            ok = _verify_rsa_signature(payload, signature_b64)
        elif algorithm in {"ED25519", "EDDSA"}:
            ok = _verify_ed25519_signature(payload, signature_b64)
        else:
            return {"valid": False, "reason": "unsupported_algorithm"}

        if not ok:
            return {"valid": False, "reason": "invalid_signature"}

        expiry = str(payload.get("expiry") or "")
        exp_date = date.fromisoformat(expiry)
        expired = exp_date < date.today()

        expected_device = str(payload.get("device_fingerprint") or "").strip()
        current_fp = device_fingerprint()
        # Support both full hash and 16-char prefix for backward compatibility/simplicity
        device_mismatch = bool(
            expected_device
            and not current_fp.startswith(expected_device)
            and expected_device != current_fp
        )

        return {
            "valid": True,
            "reason": "ok",
            "payload": payload,
            "plan": str(payload.get("plan") or "PRO"),
            "status": _normalize_license_status(payload.get("status")),
            "expired": expired,
            "device_mismatch": device_mismatch,
            "algorithm": algorithm,
        }
    except Exception as exc:
        return {"valid": False, "reason": f"invalid:{exc.__class__.__name__}"}


def _ensure_trial(trial_path: Path) -> Dict[str, Any]:
    trial_path.parent.mkdir(parents=True, exist_ok=True)
    if trial_path.exists():
        try:
            data = _load_json(trial_path)
            if "start" in data:
                return data
        except Exception:
            pass

    data = {"start": date.today().isoformat()}
    trial_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def load_runtime_license_state(
    *,
    license_path: Path,
    trial_path: Path,
    trial_days: int = 14,
) -> Dict[str, Any]:
    info = load_license(license_path)
    if info.get("valid"):
        expired = bool(info.get("expired", False))
        device_mismatch = bool(info.get("device_mismatch", False))
        status = _normalize_license_status(info.get("status"))
        read_only = expired or device_mismatch or status == "blocked"
        reason = "ok"
        if expired:
            reason = "license_expired"
        elif device_mismatch:
            reason = "device_mismatch"
        elif status == "blocked":
            reason = "license_blocked"
        elif status == "grace":
            reason = "grace"
        state = LicenseState(
            plan=str(info.get("plan") or "PRO"),
            trial=False,
            trial_days_left=0,
            expired=expired,
            device_mismatch=device_mismatch,
            read_only=read_only,
            reason=reason,
            status=status,
        )
        return state.as_dict()

    trial = _ensure_trial(trial_path)
    start = date.fromisoformat(str(trial["start"]))
    elapsed = (date.today() - start).days
    days_left = max(0, trial_days - elapsed)
    expired = elapsed >= trial_days
    state = LicenseState(
        plan="TRIAL",
        trial=True,
        trial_days_left=days_left,
        expired=expired,
        device_mismatch=False,
        read_only=expired,
        reason="trial_expired" if expired else "trial",
        status="grace" if not expired else "blocked",
    )
    return state.as_dict()
