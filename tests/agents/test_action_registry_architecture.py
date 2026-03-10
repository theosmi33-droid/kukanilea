from __future__ import annotations

from pathlib import Path

from kukanilea.orchestrator.action_catalog import (
    create_action_registry,
    derived_registry_artifact,
    registry_summary,
)
from kukanilea.orchestrator.action_registry import (
    ActionPolicyMetadata,
    ActionRegistry,
    ActionSpec,
    canonical_action_id,
    detect_duplicate_action_ids,
)


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


def test_generated_actions_have_no_duplicates() -> None:
    registry = create_action_registry()

    duplicates = detect_duplicate_action_ids(registry.actions.values())

    assert duplicates == ()


def test_write_actions_require_confirm_and_audit() -> None:
    registry = create_action_registry()

    for spec in registry.actions.values():
        if spec.is_write:
            assert spec.policy.confirm_required is True
            assert spec.policy.audit_required is True


def test_registry_stats_are_plausible_and_derived_artifact_is_valid() -> None:
    registry = create_action_registry()
    stats = registry.stats()
    artifact = derived_registry_artifact()

    assert stats.registered_actions == stats.derivable_action_ids
    assert stats.write_actions > 0
    assert stats.external_actions > 0
    assert stats.write_actions < stats.registered_actions
    assert stats.external_actions <= stats.write_actions

    assert artifact["validation"]["valid"] is True
    assert artifact["validation"]["duplicate_action_ids"] == []
    assert artifact["validation"]["incomplete_policy_action_ids"] == []
    assert artifact["validation"]["non_derivable_action_ids"] == []


def test_invoice_due_contract_sanitizes_untrusted_due_date_fields() -> None:
    source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
    assert '_extract_untrusted_text(p, "invoice_due_date")' in source
    assert '_extract_untrusted_text(p, "default_due_date")' in source


def test_manager_agent_runtime_guard_contract_has_no_neutral_downgrade_path() -> None:
    source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
    assert "warning_matches = sorted(set(warning_matches + injection_matches))" not in source


def test_manager_agent_contract_emits_missing_context_audit_payload() -> None:
    source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
    assert "\"missing_context\": list(plan.missing_context)" in source
    assert "\"manager_agent.needs_clarification\"" in source


def test_cross_tool_flows_failure_contract_avoids_traceback_field() -> None:
    source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
    assert '"traceback":' not in source
