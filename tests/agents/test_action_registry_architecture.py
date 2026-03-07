from __future__ import annotations

from kukanilea.orchestrator.action_catalog import create_action_registry, registry_summary
from kukanilea.orchestrator.action_registry import ActionRegistry, ActionSpec, ActionPolicyMetadata, canonical_action_id


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


def test_registry_external_actions_are_high_risk_and_confirmed() -> None:
    registry = create_action_registry()
    external_actions = [spec for spec in registry.actions.values() if spec.policy.external_call]

    assert external_actions, "expected at least one external action in generated registry"
    assert all(spec.policy.risk == "high" for spec in external_actions)
    assert all(spec.policy.confirm_required is True for spec in external_actions)
    assert all(spec.policy.audit_required is True for spec in external_actions)


def test_registry_action_ids_match_canonical_components() -> None:
    registry = create_action_registry()
    for action_id, spec in registry.actions.items():
        assert action_id == canonical_action_id(spec.domain, spec.entity, spec.verb, spec.modifiers)
