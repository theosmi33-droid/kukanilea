from __future__ import annotations

from kukanilea.idempotency import IdempotencyStore


def test_idempotency_store_evicts_when_capacity_reached() -> None:
    store = IdempotencyStore(max_entries=2)

    first = store.begin(scope="tool", key="k1", request_hash="h1", ttl_seconds=3600)
    store.complete_success(
        scope="tool",
        key="k1",
        token=str(first.token),
        response={"ok": True, "tool": "tool", "name": "a", "result": {"value": 1}},
        status_code=200,
        ttl_seconds=3600,
    )

    second = store.begin(scope="tool", key="k2", request_hash="h2", ttl_seconds=3600)
    store.complete_success(
        scope="tool",
        key="k2",
        token=str(second.token),
        response={"ok": True, "tool": "tool", "name": "a", "result": {"value": 2}},
        status_code=200,
        ttl_seconds=3600,
    )

    third = store.begin(scope="tool", key="k3", request_hash="h3", ttl_seconds=3600)
    assert third.status == "proceed"

    replay_first = store.begin(scope="tool", key="k1", request_hash="h1", ttl_seconds=3600)
    assert replay_first.status == "proceed"


def test_idempotency_store_truncates_large_cached_responses() -> None:
    store = IdempotencyStore(max_response_bytes=1024)

    decision = store.begin(scope="tool", key="huge", request_hash="h1", ttl_seconds=3600)
    store.complete_success(
        scope="tool",
        key="huge",
        token=str(decision.token),
        response={"ok": True, "tool": "tool", "name": "create", "result": {"blob": "x" * 5000}},
        status_code=200,
        ttl_seconds=3600,
    )

    replay = store.begin(scope="tool", key="huge", request_hash="h1", ttl_seconds=3600)
    assert replay.status == "replay"
    assert replay.response == {
        "ok": True,
        "tool": "tool",
        "name": "create",
        "result": {"truncated": True},
    }
