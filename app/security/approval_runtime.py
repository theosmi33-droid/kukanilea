from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer

from app.logging.structured_logger import log_event


@dataclass(frozen=True)
class RuntimeApprovalPolicy:
    requires_confirm: bool
    risk_level: str
    approval_scope: str
    approval_ttl_seconds: int
    approval_subject: str


class _ApprovalNonceStore:
    """In-process nonce store for one-time approval token consumption."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._issued: dict[str, float] = {}

    def issue(self, nonce: str, expires_at: float) -> None:
        with self._lock:
            self._gc_locked(now=time.time())
            self._issued[nonce] = expires_at

    def consume(self, nonce: str, *, now: float) -> bool:
        with self._lock:
            self._gc_locked(now=now)
            expiry = self._issued.get(nonce)
            if expiry is None:
                return False
            if expiry < now:
                del self._issued[nonce]
                return False
            del self._issued[nonce]
            return True

    def _gc_locked(self, *, now: float) -> None:
        expired = [key for key, exp in self._issued.items() if exp < now]
        for key in expired:
            self._issued.pop(key, None)


_NONCES = _ApprovalNonceStore()


def _serializer() -> URLSafeSerializer:
    secret = str(current_app.config.get("SECRET_KEY") or "")
    if not secret:
        raise RuntimeError("SECRET_KEY required for approval runtime")
    return URLSafeSerializer(secret_key=secret, salt="kukanilea-runtime-approval")


def _now() -> float:
    return time.time()


def _audit(status: str, *, policy: RuntimeApprovalPolicy, meta: Mapping[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "scope": policy.approval_scope,
        "subject": policy.approval_subject,
        "risk_level": policy.risk_level,
        "requires_confirm": policy.requires_confirm,
    }
    if meta:
        payload.update(dict(meta))
    log_event("approval_challenge", payload)


def create_approval_challenge(policy: RuntimeApprovalPolicy) -> str:
    nonce = secrets.token_urlsafe(18)
    issued_at = int(_now())
    ttl = max(1, int(policy.approval_ttl_seconds))
    expires_at = issued_at + ttl
    _NONCES.issue(nonce, expires_at)
    token = _serializer().dumps(
        {
            "nonce": nonce,
            "scope": policy.approval_scope,
            "subject": policy.approval_subject,
            "risk": policy.risk_level,
            "iat": issued_at,
            "exp": expires_at,
        }
    )
    _audit("created", policy=policy, meta={"nonce": nonce, "expires_at": expires_at})
    return token


def validate_approval_token(*, approval_token: str | None, policy: RuntimeApprovalPolicy) -> tuple[bool, str]:
    if not policy.requires_confirm:
        return True, "not_required"

    token = str(approval_token or "").strip()
    if not token:
        _audit("rejected", policy=policy, meta={"reason": "missing_token"})
        return False, "missing_token"

    try:
        payload = _serializer().loads(token)
    except BadSignature:
        _audit("rejected", policy=policy, meta={"reason": "invalid_signature"})
        return False, "invalid_token"

    now = _now()
    nonce = str(payload.get("nonce") or "").strip()
    scope = str(payload.get("scope") or "")
    subject = str(payload.get("subject") or "")
    risk = str(payload.get("risk") or "")
    exp = int(payload.get("exp") or 0)

    if not nonce or scope != policy.approval_scope or subject != policy.approval_subject or risk != policy.risk_level:
        _audit("rejected", policy=policy, meta={"reason": "scope_mismatch"})
        return False, "scope_mismatch"

    if exp < int(now):
        _audit("expired", policy=policy, meta={"nonce": nonce, "expires_at": exp})
        return False, "expired"

    if not _NONCES.consume(nonce, now=now):
        _audit("rejected", policy=policy, meta={"reason": "nonce_unknown_or_reused", "nonce": nonce})
        return False, "invalid_or_reused"

    _audit("confirmed", policy=policy, meta={"nonce": nonce})
    return True, "approved"
