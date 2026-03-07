from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kukanilea.orchestrator import ApprovalRuntime


def test_pending_approval_returns_pending_reason() -> None:
    runtime = ApprovalRuntime()
    challenge = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "Task"},
    )

    decision = runtime.evaluate(
        approval_id=challenge.challenge_id,
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "Task"},
    )

    assert decision.allowed is False
    assert decision.reason == "approval_pending"


def test_scope_specific_ttl_is_applied_and_expires_approval() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def _now() -> datetime:
        return now

    runtime = ApprovalRuntime(ttl_seconds=300, scope_ttl_seconds={"write": 30}, now_fn=_now)
    challenge = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "Task"},
    )
    assert challenge.expires_at == now + timedelta(seconds=30)

    approved = runtime.approve(challenge.challenge_id, tenant="KUKANILEA", approver_user="sec-admin")
    assert approved is not None

    now = now + timedelta(seconds=31)
    decision = runtime.evaluate(
        approval_id=challenge.challenge_id,
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "Task"},
    )

    assert decision.allowed is False
    assert decision.reason == "approval_expired"
