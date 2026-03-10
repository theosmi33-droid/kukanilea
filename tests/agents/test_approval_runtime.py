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


def test_evaluate_without_approval_id_creates_challenge() -> None:
    runtime = ApprovalRuntime()

    decision = runtime.evaluate(
        approval_id=None,
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "Task"},
    )

    assert decision.allowed is False
    assert decision.reason == "approval_required"
    assert decision.challenge_id is not None
    assert decision.challenge_id in runtime._challenges


def test_cleanup_prunes_denied_and_expired_entries_before_new_challenge() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def _now() -> datetime:
        return now

    runtime = ApprovalRuntime(ttl_seconds=10, now_fn=_now)
    denied = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "denied"},
    )
    expired = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "expired"},
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
    assert denied.challenge_id not in runtime._challenges
    assert expired.challenge_id not in runtime._challenges


def test_cleanup_keeps_active_pending_and_approved_entries() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def _now() -> datetime:
        return now

    runtime = ApprovalRuntime(ttl_seconds=60, now_fn=_now)
    pending = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "pending"},
    )
    approved = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "approved"},
    )
    runtime.approve(approved.challenge_id, tenant="KUKANILEA", approver_user="sec-admin")

    runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "fresh"},
    )

    assert pending.challenge_id in runtime._challenges
    assert approved.challenge_id in runtime._challenges


def test_challenge_store_is_bounded_to_max_challenges() -> None:
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


def test_size_limit_prefers_approved_over_pending_when_eviction_is_needed() -> None:
    runtime = ApprovalRuntime(max_challenges=2)
    approved = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "approved"},
    )
    runtime.approve(approved.challenge_id, tenant="KUKANILEA", approver_user="sec-admin")
    pending = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "pending"},
    )
    latest = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "latest"},
    )

    assert approved.challenge_id in runtime._challenges
    assert pending.challenge_id not in runtime._challenges
    assert latest.challenge_id in runtime._challenges


def test_spam_without_approval_id_stays_bounded() -> None:
    runtime = ApprovalRuntime(max_challenges=32)
    for idx in range(200):
        runtime.evaluate(
            approval_id=None,
            tenant="KUKANILEA",
            user="alice",
            action_id="tasks.task.create",
            scope="write",
            params={"title": f"task-{idx}"},
        )

    assert len(runtime._challenges) == 32


def test_evicted_challenge_is_not_found_on_followup_evaluate() -> None:
    runtime = ApprovalRuntime(max_challenges=1)
    first = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "one"},
    )
    runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "two"},
    )

    decision = runtime.evaluate(
        approval_id=first.challenge_id,
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "one"},
    )
    assert decision.allowed is False
    assert decision.reason == "approval_not_found"


def test_cleanup_removes_expired_approved_entries() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    def _now() -> datetime:
        return now

    runtime = ApprovalRuntime(ttl_seconds=5, now_fn=_now)
    approved = runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "approved"},
    )
    runtime.approve(approved.challenge_id, tenant="KUKANILEA", approver_user="sec-admin")

    now = now + timedelta(seconds=6)
    runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "fresh"},
    )

    assert approved.challenge_id not in runtime._challenges


def test_max_challenges_is_clamped_to_one() -> None:
    runtime = ApprovalRuntime(max_challenges=0)
    runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "one"},
    )
    runtime.create_challenge(
        tenant="KUKANILEA",
        user="alice",
        action_id="tasks.task.create",
        scope="write",
        params={"title": "two"},
    )

    assert runtime.max_challenges == 1
    assert len(runtime._challenges) == 1
