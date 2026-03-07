from __future__ import annotations

from collections.abc import Callable

import pytest

from app.core.action_executor import ActionExecutor
from app.tools.action_registry import action_registry


def _register_action(
    name: str,
    *,
    is_critical: bool,
    required: list[str] | None = None,
    tool_name: str = "demo_tool",
    action_type: str | None = None,
) -> None:
    class _InlineTool:
        def __init__(self, tool_name: str, action_name: str, action_type: str | None) -> None:
            self.name = tool_name
            self._action_name = action_name
            self._action_type = action_type

        def actions(self) -> list[dict[str, object]]:
            res = {
                "name": self._action_name,
                "inputs_schema": {
                    "type": "object",
                    "required": list(required or []),
                    "properties": {field: {"type": "string"} for field in (required or [])},
                },
                "permissions": ["admin"] if is_critical else ["operator"],
                "is_critical": is_critical,
                "audit_fields": list(required or []),
            }
            if self._action_type:
                res["action_type"] = self._action_type
            return [res]

    action_registry.register_tool(_InlineTool(tool_name, name, action_type))


@pytest.fixture()
def isolated_registry() -> None:
    previous = dict(action_registry._actions_by_name)
    action_registry._actions_by_name.clear()
    try:
        yield
    finally:
        action_registry._actions_by_name.clear()
        action_registry._actions_by_name.update(previous)


@pytest.fixture()
def executor() -> ActionExecutor:
    return ActionExecutor()


def test_registry_schema_blocks_missing_required_field(isolated_registry: None, executor: ActionExecutor) -> None:
    _register_action("secure.vault.write", is_critical=False, required=["token", "tenant_id"])

    plan = {
        "steps": [
            {
                "tool": "secure.vault.write",
                "action_type": "write",
                "params": {"token": "only-one-field"},
            }
        ]
    }

    result = executor.execute_plan(plan, dry_run=False)
    if result["status"] == "confirmation_required":
        proposal_id = result["proposal_id"]
        assert executor.confirm(proposal_id, approved=True) is True
        result = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)

    assert result["status"] == "ok"
    assert result["results"][0]["status"] == "validation_failed"
    assert executor.audit_log[-1]["status"] == "validation_failed"


def test_non_registry_tools_remain_compatible(executor: ActionExecutor) -> None:
    plan = {
        "steps": [
            {
                "tool": "dynamic.custom.action",
                "action_type": "read",
                "params": {"any": "value"},
            }
        ]
    }

    result = executor.execute_plan(plan, dry_run=False)

    assert result["status"] == "ok"
    assert result["results"][0]["status"] == "tool_not_found"


def test_critical_action_requires_confirmation(isolated_registry: None, executor: ActionExecutor) -> None:
    _register_action("billing.invoice.send", is_critical=True, required=["invoice_id"])

    plan = {
        "steps": [
            {
                "tool": "billing.invoice.send",
                "action_type": "write",
                "params": {"invoice_id": "INV-1"},
            }
        ]
    }

    pending = executor.execute_plan(plan, dry_run=False)

    assert pending["status"] == "confirmation_required"
    assert pending["proposal_id"].startswith("proposal-")
    assert len(executor.audit_log) == 1
    assert executor.audit_log[0]["status"] == "awaiting_confirmation"


def test_critical_action_executes_after_approval(isolated_registry: None, executor: ActionExecutor) -> None:
    _register_action("billing.invoice.send", is_critical=True, required=["invoice_id"])

    called: list[dict[str, str]] = []

    def _send_invoice(params: dict[str, str]) -> str:
        called.append(dict(params))
        return "sent"

    executor.register_tool("billing.invoice.send", _send_invoice)

    plan = {
        "steps": [
            {
                "tool": "billing.invoice.send",
                "action_type": "write",
                "params": {"invoice_id": "INV-42"},
            }
        ]
    }

    pending = executor.execute_plan(plan, dry_run=False)
    proposal_id = pending["proposal_id"]

    assert executor.confirm(proposal_id, approved=True) is True

    executed = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)

    assert executed["status"] == "ok"
    assert executed["results"][0]["status"] == "executed"
    assert executed["results"][0]["output"] == "sent"
    assert called == [{"invoice_id": "INV-42"}]
    assert executor.audit_log[-1]["status"] == "executed"


def test_confirmation_reject_discards_pending(isolated_registry: None, executor: ActionExecutor) -> None:
    _register_action("settings.users.delete", is_critical=True, required=["username"])

    plan = {
        "steps": [
            {
                "tool": "settings.users.delete",
                "action_type": "high_risk",
                "params": {"username": "legacy-user"},
            }
        ]
    }

    pending = executor.execute_plan(plan, dry_run=False)
    proposal_id = pending["proposal_id"]

    assert executor.confirm(proposal_id, approved=False) is False

    response = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)

    assert response["status"] in ("confirmation_missing", "proposal_not_found")
    assert response["proposal_id"] == proposal_id


@pytest.mark.parametrize(
    "action_type,is_critical,expect_confirm",
    [
        ("read", False, False),
        ("write", False, True),
        ("high_risk", False, True),
        ("read", True, True),
    ],
)
def test_confirmation_policy_matrix(
    isolated_registry: None,
    action_type: str,
    is_critical: bool,
    expect_confirm: bool,
) -> None:
    action_name = f"matrix.demo.{action_type}.{int(is_critical)}"
    # Provide action_type explicitly for the registry
    _register_action(action_name, is_critical=is_critical, required=["token"], action_type=action_type)
    executor = ActionExecutor(tools={action_name: lambda _: "ok"})

    plan = {
        "steps": [
            {
                "tool": action_name,
                "action_type": action_type,
                "params": {"token": "t"},
            }
        ]
    }

    result = executor.execute_plan(plan, dry_run=False)

    if expect_confirm:
        assert result["status"] == "confirmation_required"
        proposal_id = result["proposal_id"]
        assert executor.confirm(proposal_id, approved=True) is True
        completed = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
        
        # If it was Level 4 (high_risk), it might need second confirmation
        if completed["status"] == "confirmation_missing" and completed.get("required_confirms") == 2:
             assert executor.confirm(proposal_id, approved=True) is True
             completed = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)

        assert completed["status"] == "ok"
        assert completed["results"][0]["status"] == "executed"
    else:
        assert result["status"] == "ok"
        assert result["results"][0]["status"] == "executed"


def test_double_confirmation_for_destructive_action(isolated_registry: None, executor: ActionExecutor) -> None:
    _register_action("system.database.purge", is_critical=True, required=["db_name"])
    
    executor.register_tool("system.database.purge", lambda _: "purged")
    
    plan = {
        "steps": [
            {
                "tool": "system.database.purge",
                "action_type": "high_risk",
                "params": {"db_name": "prod_backup"},
            }
        ]
    }
    
    # 1. First execution attempt -> confirmation required
    res1 = executor.execute_plan(plan, dry_run=False)
    assert res1["status"] == "confirmation_required"
    assert res1["level"] == 4
    proposal_id = res1["proposal_id"]
    
    # 2. First confirmation
    assert executor.confirm(proposal_id, approved=True) is True
    
    # 3. Second execution attempt -> still missing one confirmation
    res2 = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
    assert res2["status"] == "confirmation_missing"
    assert res2["current_confirms"] == 1
    assert res2["required_confirms"] == 2
    
    # 4. Second confirmation
    assert executor.confirm(proposal_id, approved=True) is True
    
    # 5. Third execution attempt -> OK
    res3 = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
    assert res3["status"] == "ok"
    assert res3["results"][0]["status"] == "executed"
    assert res3["results"][0]["output"] == "purged"


@pytest.mark.parametrize(
    "required_fields,params,expected_status",
    [
        (["a"], {"a": "x"}, "executed"),
        (["a", "b"], {"a": "x"}, "validation_failed"),
        ([], {}, "executed"),
    ],
)
def test_schema_required_matrix(
    isolated_registry: None,
    required_fields: list[str],
    params: dict[str, str],
    expected_status: str,
) -> None:
    action_name = f"schema.matrix.{len(required_fields)}"
    _register_action(action_name, is_critical=False, required=required_fields)

    called: list[dict[str, str]] = []

    def _handler(payload: dict[str, str]) -> str:
        called.append(dict(payload))
        return "ok"

    executor = ActionExecutor(tools={action_name: _handler})
    plan = {
        "steps": [
            {
                "tool": action_name,
                "action_type": "write",
                "params": params,
            }
        ]
    }

    result = executor.execute_plan(plan, dry_run=False)

    if result["status"] == "confirmation_required":
        proposal_id = result["proposal_id"]
        executor.confirm(proposal_id, approved=True)
        result = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)

    assert result["status"] == "ok"
    assert result["results"][0]["status"] == expected_status
    if expected_status == "executed":
        assert called == [params]
    else:
        assert called == []


def test_dry_run_never_executes_handlers(isolated_registry: None) -> None:
    action_name = "dry.run.demo"
    _register_action(action_name, is_critical=True, required=["id"])

    called = False

    def _handler(_: dict[str, str]) -> str:
        nonlocal called
        called = True
        return "should_not_happen"

    executor = ActionExecutor(tools={action_name: _handler})
    plan = {
        "steps": [
            {
                "tool": action_name,
                "action_type": "high_risk",
                "params": {"id": "X"},
            }
        ]
    }

    result = executor.execute_plan(plan, dry_run=True)

    assert result["status"] == "ok"
    assert result["results"][0]["status"] == "dry_run"
    assert called is False


@pytest.mark.parametrize("approved", [True, False])
def test_confirm_returns_false_for_unknown_proposal(approved: bool, executor: ActionExecutor) -> None:
    assert executor.confirm("proposal-does-not-exist", approved=approved) is False
