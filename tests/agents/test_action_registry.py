from __future__ import annotations

from pathlib import Path

from app.agents.action_manager import ActionManager
from app.core.tool_loader import load_all_tools
from app.tools.action_registry import action_registry
from app.tools.registry import registry


def _ensure_loaded() -> None:
    if not registry.list():
        load_all_tools()


def test_each_tool_registers_at_least_20_actions() -> None:
    _ensure_loaded()
    summary = action_registry.tools_summary()
    assert summary
    assert all(count >= 20 for count in summary.values())


def test_action_registry_count_matches_tool_summary() -> None:
    _ensure_loaded()
    summary = action_registry.tools_summary()
    assert action_registry.count() == sum(summary.values())


def test_manager_can_list_search_and_compose_with_events() -> None:
    _ensure_loaded()
    manager = ActionManager()

    listed = manager.list_actions()
    assert listed

    critical = manager.search_actions("execute", critical_only=True)
    assert critical
    assert all(item["is_critical"] for item in critical)

    workflow = manager.compose_workflow(
        [
            {
                "action": listed[0]["name"],
                "params": {"tenant_id": "default"},
                "emit_event": "action.completed",
            },
            {
                "action": listed[1]["name"],
                "params": {},
            },
        ]
    )
    assert workflow["action_count"] == 2
    assert workflow["events"] == [
        {
            "type": "action.completed",
            "source_action": listed[0]["name"],
            "step_index": 0,
        }
    ]


def test_invoice_flow_contract_uses_untrusted_extraction_guard() -> None:
    source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
    assert '"invoice_extract_due"' in source
    assert '_extract_untrusted_text(p, "invoice_id")' in source


def test_manager_agent_contract_keeps_prompt_injection_blocking_in_neutral_context() -> None:
    source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
    assert "if injection_matches:" in source
    assert "neutral_context = bool(" not in source


def test_manager_agent_contract_blocks_action_routing_when_context_is_missing() -> None:
    source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
    assert 'reason="missing_context"' in source
    assert "plan.missing_context or plan.execution_mode == \"propose\"" in source
