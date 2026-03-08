from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ApprovalChallenge:
    challenge_id: str
    tenant: str
    requested_by: str
    action_id: str
    scope: str
    params_fingerprint: str
    status: str
    created_at: datetime
    expires_at: datetime
    approved_at: datetime | None = None
    approved_by: str | None = None
    denied_at: datetime | None = None
    denied_by: str | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    reason: str
    challenge_id: str | None = None


class ApprovalRuntime:
    """Server-side approval runtime with strict scope/action/user/tenant checks."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 300,
        scope_ttl_seconds: Mapping[str, int] | None = None,
        max_challenges: int = 4096,
        now_fn: Callable[[], datetime] | None = None,
        audit_logger: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_challenges = max(1, int(max_challenges))
        self.scope_ttl_seconds = {
            str(scope): max(1, int(scope_ttl)) for scope, scope_ttl in dict(scope_ttl_seconds or {}).items()
        }
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._audit_logger = audit_logger
        self._challenges: dict[str, ApprovalChallenge] = {}

    def evaluate(
        self,
        *,
        approval_id: str | None,
        tenant: str,
        user: str,
        action_id: str,
        scope: str,
        params: Mapping[str, Any] | None,
    ) -> ApprovalDecision:
        if not approval_id:
            challenge = self.create_challenge(tenant=tenant, user=user, action_id=action_id, scope=scope, params=params)
            return ApprovalDecision(False, "approval_required", challenge.challenge_id)

        challenge = self._challenges.get(str(approval_id))
        if challenge is None:
            return ApprovalDecision(False, "approval_not_found")

        if self._is_expired(challenge):
            self._expire(challenge)
            return ApprovalDecision(False, "approval_expired", challenge.challenge_id)

        if challenge.status == "denied":
            return ApprovalDecision(False, "approval_denied", challenge.challenge_id)

        if challenge.status != "approved":
            return ApprovalDecision(False, "approval_pending", challenge.challenge_id)

        if challenge.tenant != tenant:
            return ApprovalDecision(False, "approval_tenant_mismatch", challenge.challenge_id)

        if challenge.requested_by != user:
            return ApprovalDecision(False, "approval_user_mismatch", challenge.challenge_id)

        if challenge.action_id != action_id:
            return ApprovalDecision(False, "approval_action_mismatch", challenge.challenge_id)

        if challenge.scope != scope:
            return ApprovalDecision(False, "approval_scope_mismatch", challenge.challenge_id)

        expected = self._fingerprint(params)
        if challenge.params_fingerprint != expected:
            return ApprovalDecision(False, "approval_params_mismatch", challenge.challenge_id)

        return ApprovalDecision(True, "approved", challenge.challenge_id)

    def create_challenge(
        self,
        *,
        tenant: str,
        user: str,
        action_id: str,
        scope: str,
        params: Mapping[str, Any] | None,
    ) -> ApprovalChallenge:
        self._cleanup()
        now = self._now_fn()
        challenge = ApprovalChallenge(
            challenge_id=f"apr_{uuid.uuid4().hex}",
            tenant=tenant,
            requested_by=user,
            action_id=action_id,
            scope=scope,
            params_fingerprint=self._fingerprint(params),
            status="pending",
            created_at=now,
            expires_at=now + timedelta(seconds=self._resolve_ttl_seconds(scope)),
        )
        self._challenges[challenge.challenge_id] = challenge
        self._enforce_size_limit()
        self._audit("approval.create", challenge)
        return challenge

    def approve(self, challenge_id: str, *, tenant: str, approver_user: str) -> ApprovalChallenge | None:
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            return None
        if challenge.tenant != tenant:
            return None
        if self._is_expired(challenge):
            self._expire(challenge)
            return None
        approved = ApprovalChallenge(
            **{
                **challenge.__dict__,
                "status": "approved",
                "approved_at": self._now_fn(),
                "approved_by": approver_user,
            }
        )
        self._challenges[challenge_id] = approved
        self._audit("approval.approve", approved)
        return approved

    def deny(self, challenge_id: str, *, tenant: str, actor_user: str) -> ApprovalChallenge | None:
        challenge = self._challenges.get(challenge_id)
        if challenge is None or challenge.tenant != tenant:
            return None
        denied = ApprovalChallenge(
            **{
                **challenge.__dict__,
                "status": "denied",
                "denied_at": self._now_fn(),
                "denied_by": actor_user,
            }
        )
        self._challenges[challenge_id] = denied
        self._audit("approval.deny", denied)
        return denied

    def _expire(self, challenge: ApprovalChallenge) -> None:
        if challenge.status == "expired":
            return
        expired = ApprovalChallenge(**{**challenge.__dict__, "status": "expired"})
        self._challenges[challenge.challenge_id] = expired
        self._audit("approval.expire", expired)

    def _cleanup(self) -> None:
        now = self._now_fn()
        expired_ids = [
            challenge_id
            for challenge_id, challenge in self._challenges.items()
            if challenge.status in {"denied", "expired"} or now >= challenge.expires_at
        ]
        for challenge_id in expired_ids:
            self._challenges.pop(challenge_id, None)

    def _enforce_size_limit(self) -> None:
        overflow = len(self._challenges) - self.max_challenges
        if overflow <= 0:
            return
        oldest = sorted(
            self._challenges.values(),
            key=lambda challenge: (challenge.created_at, challenge.challenge_id),
        )
        for challenge in oldest[:overflow]:
            self._challenges.pop(challenge.challenge_id, None)

    def _audit(self, event: str, challenge: ApprovalChallenge) -> None:
        if not callable(self._audit_logger):
            return
        self._audit_logger(
            {
                "event": event,
                "challenge_id": challenge.challenge_id,
                "tenant": challenge.tenant,
                "requested_by": challenge.requested_by,
                "action_id": challenge.action_id,
                "scope": challenge.scope,
                "status": challenge.status,
                "expires_at": challenge.expires_at.isoformat(),
            }
        )

    def _is_expired(self, challenge: ApprovalChallenge) -> bool:
        return self._now_fn() >= challenge.expires_at

    def _resolve_ttl_seconds(self, scope: str) -> int:
        return self.scope_ttl_seconds.get(str(scope), self.ttl_seconds)

    @staticmethod
    def _fingerprint(params: Mapping[str, Any] | None) -> str:
        payload = json.dumps(dict(params or {}), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
