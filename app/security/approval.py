from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable

WRITE_ACTION_PREFIXES = ("create_", "delete_", "update_", "send_", "mail_", "messenger_")
WRITE_ACTIONS = {
    "create_task",
    "create_appointment",
    "mail_send",
    "messenger_send",
    "mail_generate",
}


@dataclass(frozen=True)
class ApprovalScope:
    tenant_id: str
    user_id: str
    action_id: str
    params_fingerprint: str = ""


@dataclass(frozen=True)
class ApprovalChallenge:
    challenge_id: str
    token: str
    scope: ApprovalScope
    expires_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(value: Any) -> str:
    return str(value or "").strip()


def build_params_fingerprint(params: dict[str, Any] | None) -> str:
    if not isinstance(params, dict) or not params:
        return ""
    pairs = []
    for key in sorted(params.keys()):
        if key in {"approval_token", "confirm", "approval_ttl"}:
            continue
        pairs.append(f"{key}={params[key]!r}")
    return "|".join(pairs)


def action_requires_approval(*, action_type: str = "", permission: str = "", risk: str = "") -> bool:
    action_name = _norm(action_type)
    normalized_permission = _norm(permission).lower()
    normalized_risk = _norm(risk).lower()
    return bool(
        normalized_permission == "write"
        or normalized_risk == "high_risk"
        or action_name in WRITE_ACTIONS
        or action_name.startswith(WRITE_ACTION_PREFIXES)
    )


class ApprovalEngine:
    def __init__(
        self,
        *,
        now_fn: Callable[[], datetime] = _utc_now,
        audit_hook: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._now_fn = now_fn
        self._audit_hook = audit_hook
        self._lock = Lock()
        self._by_token: dict[str, ApprovalChallenge] = {}

    def _audit(self, event: str, meta: dict[str, Any]) -> None:
        if self._audit_hook:
            self._audit_hook(event, meta)

    def request_challenge(self, *, scope: ApprovalScope, ttl_seconds: int = 300) -> ApprovalChallenge:
        ttl = max(1, int(ttl_seconds))
        now = self._now_fn()
        challenge = ApprovalChallenge(
            challenge_id=secrets.token_urlsafe(16),
            token=secrets.token_urlsafe(24),
            scope=scope,
            expires_at=now + timedelta(seconds=ttl),
        )
        with self._lock:
            self._by_token[challenge.token] = challenge
        meta = {
            "challenge_id": challenge.challenge_id,
            "tenant_id": scope.tenant_id,
            "user_id": scope.user_id,
            "action_id": scope.action_id,
            "expires_at": challenge.expires_at.isoformat(),
        }
        self._audit("approval.request", meta)
        return challenge

    def validate(self, *, token: str | None, scope: ApprovalScope) -> tuple[bool, str]:
        normalized = _norm(token)
        if not normalized:
            self._audit(
                "approval.deny",
                {
                    "reason": "missing_token",
                    "tenant_id": scope.tenant_id,
                    "user_id": scope.user_id,
                    "action_id": scope.action_id,
                },
            )
            return False, "missing_token"

        with self._lock:
            challenge = self._by_token.get(normalized)

        if challenge is None:
            self._audit(
                "approval.deny",
                {
                    "reason": "unknown_token",
                    "tenant_id": scope.tenant_id,
                    "user_id": scope.user_id,
                    "action_id": scope.action_id,
                },
            )
            return False, "unknown_token"

        now = self._now_fn()
        if now >= challenge.expires_at:
            self._audit(
                "approval.expire",
                {
                    "challenge_id": challenge.challenge_id,
                    "tenant_id": scope.tenant_id,
                    "user_id": scope.user_id,
                    "action_id": scope.action_id,
                },
            )
            return False, "expired"

        if challenge.scope != scope:
            self._audit(
                "approval.deny",
                {
                    "reason": "scope_mismatch",
                    "challenge_id": challenge.challenge_id,
                    "tenant_id": scope.tenant_id,
                    "user_id": scope.user_id,
                    "action_id": scope.action_id,
                },
            )
            return False, "scope_mismatch"

        self._audit(
            "approval.grant",
            {
                "challenge_id": challenge.challenge_id,
                "tenant_id": scope.tenant_id,
                "user_id": scope.user_id,
                "action_id": scope.action_id,
            },
        )
        return True, "granted"
