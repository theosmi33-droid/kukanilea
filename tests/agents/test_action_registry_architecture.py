from __future__ import annotations

from kukanilea.orchestrator.action_catalog import create_action_registry, registry_summary
from kukanilea.orchestrator.action_registry import ActionRegistry, ActionSpec, canonical_action_id


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
        confirm_required=False,
        audit_required=False,
        risk="medium",
        external_call=False,
        idempotency="non_idempotent",
    )
    registry.register(invalid_write)

    try:
        registry.validate()
    except ValueError as exc:
        assert "Write action without confirm+audit policy" in str(exc)
    else:
        raise AssertionError("validation should fail for write actions without policy gates")


def test_registry_validation_rejects_high_impact_action_without_high_risk() -> None:
    registry = ActionRegistry()
    invalid_risk = ActionSpec(
        action_id="mail.mail.send",
        domain="mail",
        entity="mail",
        verb="send",
        modifiers=(),
        tool="mail",
        parameter_schema={"message": "str"},
        confirm_required=True,
        audit_required=True,
        risk="medium",
        external_call=True,
        idempotency="non_idempotent",
    )
    registry.register(invalid_risk)

    try:
        registry.validate()
    except ValueError as exc:
        assert "High-impact/external action without high risk classification" in str(exc)
    else:
        raise AssertionError("validation should fail for high-impact/external low-risk actions")


def test_registry_validation_rejects_derivation_mismatch() -> None:
    registry = create_action_registry()
    action = registry.actions.pop("crm.customer.read")
    registry.actions["crm.customer.read.broken"] = action

    try:
        registry.validate()
    except ValueError as exc:
        assert "Derivation mismatch in domain 'crm'" in str(exc)
    else:
        raise AssertionError("validation should fail when derivation and registered ids diverge")
