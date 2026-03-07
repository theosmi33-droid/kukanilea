from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.security.approval import (
    MAX_APPROVAL_TTL_SECONDS,
    ApprovalEngine,
    ApprovalScope,
    build_params_fingerprint,
)


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_build_params_fingerprint_uses_canonical_hash():
    left = {"a": "b", "c": "d"}
    right = {"a='b'|c": "d"}

    assert build_params_fingerprint(left) != build_params_fingerprint(right)
    assert build_params_fingerprint({"x": 1, "y": 2}) == build_params_fingerprint({"y": 2, "x": 1})


def test_approval_engine_tokens_are_single_use():
    clock = Clock(datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc))
    engine = ApprovalEngine(now_fn=clock)
    scope = ApprovalScope(tenant_id="KUKANILEA", user_id="u1", action_id="aufgaben.create")

    challenge = engine.request_challenge(scope=scope, ttl_seconds=60)

    ok, reason = engine.validate(token=challenge.token, scope=scope)
    assert ok is True
    assert reason == "granted"

    ok2, reason2 = engine.validate(token=challenge.token, scope=scope)
    assert ok2 is False
    assert reason2 == "unknown_token"


def test_approval_engine_scope_mismatch_does_not_consume_token():
    clock = Clock(datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc))
    engine = ApprovalEngine(now_fn=clock)
    scope = ApprovalScope(tenant_id="KUKANILEA", user_id="u1", action_id="aufgaben.create")
    challenge = engine.request_challenge(scope=scope, ttl_seconds=60)

    mismatch = ApprovalScope(tenant_id="KUKANILEA", user_id="u1", action_id="aufgaben.update")
    denied, reason = engine.validate(token=challenge.token, scope=mismatch)
    assert denied is False
    assert reason == "scope_mismatch"

    granted, reason2 = engine.validate(token=challenge.token, scope=scope)
    assert granted is True
    assert reason2 == "granted"


def test_approval_engine_caps_ttl_and_prunes_expired_tokens():
    clock = Clock(datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc))
    engine = ApprovalEngine(now_fn=clock)
    scope = ApprovalScope(tenant_id="KUKANILEA", user_id="u1", action_id="aufgaben.create")

    challenge = engine.request_challenge(scope=scope, ttl_seconds=10_000)
    assert challenge.expires_at <= clock.now + timedelta(seconds=MAX_APPROVAL_TTL_SECONDS)

    # Move time forward so challenge is expired and ensure it cannot be validated anymore.
    clock.now = clock.now + timedelta(seconds=MAX_APPROVAL_TTL_SECONDS + 1)
    denied, reason = engine.validate(token=challenge.token, scope=scope)
    assert denied is False
    assert reason == "expired"
