from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict

# Ed25519 public key used to validate offline license signatures.
# Matching private key is kept internal and only used by scripts/generate_license.py.
PUBLIC_KEY_HEX = "d9213284c379d7ffd915619a57d2105fa4f39bbf2b25fa39d1d189bd57778b07"

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except Exception:  # pragma: no cover - optional at import time
    Ed25519PublicKey = None  # type: ignore


@dataclass
class LicenseState:
    plan: str
    trial: bool
    trial_days_left: int
    expired: bool
    device_mismatch: bool
    read_only: bool
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "plan": self.plan,
            "trial": self.trial,
            "trial_days_left": self.trial_days_left,
            "expired": self.expired,
            "device_mismatch": self.device_mismatch,
            "read_only": self.read_only,
            "reason": self.reason,
        }


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


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

        payload = dict(raw)
        payload.pop("signature", None)

        if Ed25519PublicKey is None:
            return {"valid": False, "reason": "missing_crypto"}

        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, _canonical_payload_bytes(payload))

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
            "expired": expired,
            "device_mismatch": device_mismatch,
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
        read_only = expired or device_mismatch
        reason = "ok"
        if expired:
            reason = "license_expired"
        elif device_mismatch:
            reason = "device_mismatch"
        state = LicenseState(
            plan=str(info.get("plan") or "PRO"),
            trial=False,
            trial_days_left=0,
            expired=expired,
            device_mismatch=device_mismatch,
            read_only=read_only,
            reason=reason,
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
    )
    return state.as_dict()
