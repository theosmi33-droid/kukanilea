from __future__ import annotations

import pytest

from kukanilea.orchestrator.action_catalog import create_action_registry, registry_summary
from kukanilea.orchestrator.action_registry import ActionPolicyMetadata, ActionRegistry, ActionSpec, canonical_action_id


def test_registry_generates_canonical_action_ids() -> None:
    registry = create_action_registry()

    assert "tasks.task.create" in registry.actions
    assert "messenger.message.reply.encrypted" in registry.actions
    assert canonical_action_id("CRM", "Customer", "Search") == "crm.customer.search"


def test_registry_scales_beyond_2000_derivable_actions() -> None:
    summary = registry_summary()

    assert summary["domains"] >= 10
    assert summary["registered_actions"] >= 2000
    assert summary["derivable_actions"] >= 2000


def test_registry_validation_rejects_write_actions_without_confirm_and_audit() -> None:
    registry = ActionRegistry()
    invalid_write = ActionSpec(
        action_id="tasks.task.create",
        domain="tasks",
        entity="task",
        verb="create",
        modifiers=(),
        tool="tasks",
        parameter_schema={"title": "str"},
        policy=ActionPolicyMetadata(
            confirm_required=False,
            audit_required=False,
            risk="medium",
            external_call=False,
            idempotency="non_idempotent",
        ),
    )
    registry.register(invalid_write)

    try:
        registry.validate()
    except ValueError as exc:
        assert "Write action without confirm+audit policy" in str(exc)
    else:
        raise AssertionError("validation should fail for write actions without policy gates")


def test_registry_resolves_legacy_alias_to_canonical_action_with_warning() -> None:
    registry = create_action_registry()

    with pytest.warns(DeprecationWarning):
        spec = registry.get("messenger.reply")

    assert spec is not None
    assert spec.action_id == "messenger.message.reply"


def test_registry_rejects_unknown_action_name_resolution() -> None:
    registry = create_action_registry()

    assert registry.resolve_action_id("legacy.unknown.action") is None
