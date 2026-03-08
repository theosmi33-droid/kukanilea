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


def test_cleanup_prunes_expired_and_denied_before_new_challenge() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def _now() -> datetime:
        return now

    runtime = ApprovalRuntime(ttl_seconds=10, now_fn=_now)
    expired = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "expired"},
    )
    denied = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "denied"},
    )
    runtime.deny(denied.challenge_id, tenant="KUKANILEA", actor_user="sec-admin")

    now = now + timedelta(seconds=11)
    fresh = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "fresh"},
    )

    assert fresh.challenge_id in runtime._challenges
    assert expired.challenge_id not in runtime._challenges
    assert denied.challenge_id not in runtime._challenges


def test_challenge_store_is_bounded() -> None:
    runtime = ApprovalRuntime(max_challenges=2)

    first = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "one"},
    )
    second = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "two"},
    )
    third = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "three"},
    )

    assert len(runtime._challenges) == 2
    assert first.challenge_id not in runtime._challenges
    assert second.challenge_id in runtime._challenges
    assert third.challenge_id in runtime._challenges
