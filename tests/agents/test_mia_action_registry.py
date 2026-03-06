from __future__ import annotations

from app.core.tool_loader import load_all_tools
from app.tools.action_registry import action_registry
from app.tools.registry import registry


def _ensure_loaded() -> None:
    if not registry.list():
        load_all_tools()


def test_registry_load_is_deterministic() -> None:
    load_all_tools()
    first = [item["action_id"] for item in action_registry.list_actions()]
    load_all_tools()
    second = [item["action_id"] for item in action_registry.list_actions()]
    assert first == second


def test_registry_has_no_duplicate_action_ids() -> None:
    _ensure_loaded()
    action_ids = [item["action_id"] for item in action_registry.list_actions()]
    assert len(action_ids) == len(set(action_ids))


def test_each_action_has_policy_metadata() -> None:
    _ensure_loaded()
    for action in action_registry.list_actions():
        assert action["risk_level"] in {"low", "medium", "high"}
        assert action["audit_event_type"]
        assert action["idempotency_key_strategy"]
        assert isinstance(action["enabled"], bool)


def test_write_actions_require_confirm_and_audit() -> None:
    _ensure_loaded()
    write_verbs = {"create", "update", "upsert", "delete", "archive", "restore", "approve", "execute", "cancel"}
    write_actions = [
        action
        for action in action_registry.list_actions()
        if action["verb"] in write_verbs
    ]
    assert write_actions
    for action in write_actions:
        assert action["requires_confirm"] is True
        assert action["audit_event_type"]


def test_registry_exposes_more_than_2000_actions() -> None:
    _ensure_loaded()
    assert action_registry.count() > 2000
