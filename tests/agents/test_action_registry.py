from __future__ import annotations

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


class _IsolatedProbeTool:
    name = "isolation_probe"

    def actions(self):
        return [
            {
                "action_id": "probe.default.get",
                "name": "probe.default.get",
                "inputs_schema": {"type": "object", "properties": {}},
                "permissions": ["tenant:read"],
                "confirm_required": False,
                "audit_required": False,
                "action_type": "read",
            }
        ]


def test_registry_mutation_in_one_test_is_not_persisted() -> None:
    before = action_registry.count()
    action_registry.register_tool(_IsolatedProbeTool())
    assert action_registry.count() == before + 1


def test_registry_starts_clean_for_followup_tests() -> None:
    assert all(item["action_id"] != "probe.default.get" for item in action_registry.list_actions())
