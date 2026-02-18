from __future__ import annotations

import base64
import hashlib
import json
import socket
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict

# Ed25519 public key used to validate offline license signatures.
# Matching private key is kept internal and only used by scripts/generate_license.py.
PUBLIC_KEY_HEX = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"

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
    grace_active: bool = False
    grace_days_left: int = 0
    validated_online: bool = False
    last_validated: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "plan": self.plan,
            "trial": self.trial,
            "trial_days_left": self.trial_days_left,
            "expired": self.expired,
            "device_mismatch": self.device_mismatch,
            "read_only": self.read_only,
            "reason": self.reason,
            "grace_active": self.grace_active,
            "grace_days_left": self.grace_days_left,
            "validated_online": self.validated_online,
            "last_validated": self.last_validated,
        }


def _canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def device_fingerprint() -> str:
    raw = f"{uuid.getnode()}::{socket.gethostname()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _safe_date(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def _load_cache(cache_path: Path, *, license_hash: str) -> dict[str, Any]:
    if not cache_path.exists():
        return {}
    try:
        raw = _load_json(cache_path)
    except Exception:
        return {}
    if str(raw.get("license_hash") or "") != str(license_hash or ""):
        return {}
    return dict(raw)


def _write_cache(cache_path: Path, payload: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _validate_license_online(
    *,
    validate_url: str,
    signed_license_payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    url = str(validate_url or "").strip()
    if not url:
        return {"request_ok": False, "reason": "validation_url_missing"}

    body = {
        "license": signed_license_payload,
        "device_fingerprint": device_fingerprint(),
        "app": "kukanilea",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "KUKANILEA/1.0",
        },
        method="POST",
    )

    status_code = 0
    raw_text = ""
    try:
        with urllib.request.urlopen(
            request, timeout=max(1, int(timeout_seconds))
        ) as resp:
            status_code = int(getattr(resp, "status", 0) or 0)
            raw_text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = int(getattr(exc, "code", 0) or 0)
        raw_text = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return {"request_ok": False, "reason": "validation_network_error"}

    payload: dict[str, Any] = {}
    if raw_text.strip():
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}

    if not payload:
        return {
            "request_ok": False,
            "reason": f"validation_http_{status_code or 0}",
        }

    valid = bool(payload.get("valid"))
    reason = str(payload.get("reason") or ("ok" if valid else "invalid_remote"))
    return {
        "request_ok": True,
        "valid": valid,
        "reason": reason,
        "tier": str(payload.get("tier") or "").strip(),
        "valid_until": str(payload.get("valid_until") or "").strip(),
    }


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
        canonical_payload = _canonical_payload_bytes(payload)
        public_key.verify(signature, canonical_payload)

        expiry = str(payload.get("expiry") or "")
        exp_date = date.fromisoformat(expiry)
        expired = exp_date < date.today()

        expected_device = str(payload.get("device_fingerprint") or "").strip()
        device_mismatch = bool(
            expected_device and expected_device != device_fingerprint()
        )

        return {
            "valid": True,
            "reason": "ok",
            "payload": payload,
            "payload_hash": hashlib.sha256(canonical_payload).hexdigest(),
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
    cache_path: Path | None = None,
    validate_url: str = "",
    validate_timeout_seconds: int = 10,
    validate_interval_days: int = 30,
    grace_days: int = 30,
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

        plan = str(info.get("plan") or "PRO")
        grace_active = False
        grace_days_left = 0
        validated_online = False
        last_validated_text = ""

        should_validate_online = bool(str(validate_url or "").strip()) and not read_only
        if should_validate_online:
            now = date.today()
            validation_interval = max(1, int(validate_interval_days))
            grace_window = max(0, int(grace_days))
            effective_cache_path = cache_path or (
                trial_path.parent / "license_cache.json"
            )
            license_hash = str(info.get("payload_hash") or "")
            cache = _load_cache(effective_cache_path, license_hash=license_hash)

            last_validated = _safe_date(str(cache.get("last_validated") or ""))
            grace_expires = _safe_date(str(cache.get("grace_expires") or ""))
            cache_status = str(cache.get("status") or "").strip().lower()
            due = (
                last_validated is None
                or (now - last_validated).days >= validation_interval
            )

            if due:
                remote = _validate_license_online(
                    validate_url=validate_url,
                    signed_license_payload=dict(info.get("payload") or {}),
                    timeout_seconds=validate_timeout_seconds,
                )
                if bool(remote.get("request_ok")):
                    validated_online = True
                    last_validated_text = now.isoformat()
                    if bool(remote.get("valid")):
                        remote_tier = str(remote.get("tier") or "").strip()
                        if remote_tier:
                            plan = remote_tier
                        remote_valid_until = _safe_date(
                            str(remote.get("valid_until") or "")
                        )
                        if remote_valid_until is not None and remote_valid_until < now:
                            read_only = True
                            reason = "license_remote_expired"
                            cache_payload = {
                                "license_hash": license_hash,
                                "status": "invalid",
                                "reason": reason,
                                "last_validated": now.isoformat(),
                                "grace_expires": now.isoformat(),
                                "plan": plan,
                            }
                        else:
                            reason = "ok"
                            cache_payload = {
                                "license_hash": license_hash,
                                "status": "active",
                                "reason": "ok",
                                "last_validated": now.isoformat(),
                                "grace_expires": (
                                    now + timedelta(days=grace_window)
                                ).isoformat(),
                                "plan": plan,
                                "remote_valid_until": str(
                                    remote.get("valid_until") or ""
                                ),
                            }
                        _write_cache(effective_cache_path, cache_payload)
                    else:
                        read_only = True
                        reason = str(remote.get("reason") or "license_invalid_remote")
                        _write_cache(
                            effective_cache_path,
                            {
                                "license_hash": license_hash,
                                "status": "invalid",
                                "reason": reason,
                                "last_validated": now.isoformat(),
                                "grace_expires": now.isoformat(),
                                "plan": plan,
                            },
                        )
                else:
                    # Remote validation unreachable: allow temporary operation in grace window.
                    reason = str(
                        remote.get("reason") or "license_validation_unreachable"
                    )
                    if grace_expires is None:
                        grace_expires = now + timedelta(days=grace_window)
                        _write_cache(
                            effective_cache_path,
                            {
                                "license_hash": license_hash,
                                "status": cache_status or "error",
                                "reason": reason,
                                "last_validated": str(
                                    cache.get("last_validated") or ""
                                ),
                                "grace_expires": grace_expires.isoformat(),
                                "plan": plan,
                            },
                        )
                    if now <= grace_expires:
                        grace_active = True
                        grace_days_left = max(0, (grace_expires - now).days)
                        reason = "license_grace_offline"
                    else:
                        read_only = True
            else:
                if last_validated is not None:
                    last_validated_text = last_validated.isoformat()
                if cache_status and cache_status != "active":
                    read_only = True
                    reason = str(cache.get("reason") or "license_invalid_remote")

        state = LicenseState(
            plan=plan,
            trial=False,
            trial_days_left=0,
            expired=expired,
            device_mismatch=device_mismatch,
            read_only=read_only,
            reason=reason,
            grace_active=grace_active,
            grace_days_left=grace_days_left,
            validated_online=validated_online,
            last_validated=last_validated_text,
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
