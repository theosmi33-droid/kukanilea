from __future__ import annotations

import pytest
from app.core.action_executor import ActionExecutor
from app.tools.action_registry import action_registry, ActionDefinition


class MockTool:
    def __init__(self, name):
        self.name = name
    def actions(self):
        return [
            {
                "name": f"{self.name}_action",
                "inputs_schema": {"type": "object", "required": ["token"], "properties": {"token": {"type": "string"}}},
                "permissions": ["admin"],
                "is_critical": True,
                "audit_fields": ["token"]
            }
        ]

def test_action_executor_enforces_registry_schema_and_critical_confirm():
    # Setup registry with a mock tool
    tool = MockTool("secure_vault")
    action_registry.register_tool(tool)
    
    executor = ActionExecutor(tools={"secure_vault_action": lambda p: "secret_data"})
    
    # Plan missing required 'token'
    plan = {
        "steps": [
            {"tool": "secure_vault_action", "params": {"wrong": "data"}}
        ]
    }
    
    # 1. Test validation failure
    # Validations are checked per step. If a step fails validation, it should be marked in results.
    # Note: execute_plan returns status: "ok" if it can process steps (even if some fail) 
    # OR status: "confirmation_required" if any step is critical.
    # We need to ensure validation happens even if it's critical.
    res = executor.execute_plan(plan, dry_run=False)
    # If it's critical, it might return confirmation_required first.
    if res["status"] == "confirmation_required":
        # Even if confirmation is required, the step validation should have been checked? 
        # Actually, in current executor, confirmation check happens BEFORE step execution.
        # Let's fix executor to validate BEFORE proposing if possible, or handle it in test.
        proposal_id = res["proposal_id"]
        executor.confirm(proposal_id, approved=True)
        res = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
    
    assert res["results"][0]["status"] == "validation_failed"
    
    # 2. Test critical confirm requirement
    plan_valid = {
        "steps": [
            {"tool": "secure_vault_action", "params": {"token": "valid_token"}}
        ]
    }
    res_confirm = executor.execute_plan(plan_valid, dry_run=False)
    assert res_confirm["status"] == "confirmation_required"
    
    # 3. Test successful execution after confirm
    proposal_id = res_confirm["proposal_id"]
    executor.confirm(proposal_id, approved=True)
    res_final = executor.execute_plan(plan_valid, dry_run=False, proposal_id=proposal_id)
    assert res_final["status"] == "ok"
    assert res_final["results"][0]["output"] == "secret_data"
