from __future__ import annotations

import pytest
from app.core.action_executor import ActionExecutor
from app.tools.action_registry import action_registry, ActionDefinition
from app.tools.base_tool import BaseTool


class SecureVaultTool(BaseTool):
    name = "secure_vault"
    domain = "SECURITY"
    entity = "VAULT"
    input_schema = {"type": "object", "required": ["token"], "properties": {"token": {"type": "string"}}}

def test_action_executor_enforces_registry_hierarchy_and_critical_confirm():
    # Setup registry with a mock tool following the new hierarchy
    tool = SecureVaultTool()
    action_registry.register_tool(tool)
    
    # Action name will be SECURITY.VAULT.EXECUTE (suffix 'execute' is critical by default)
    action_name = "SECURITY.VAULT.EXECUTE"
    assert action_name in action_registry._actions_by_name
    
    executor = ActionExecutor(tools={action_name: lambda p: "secret_data"})
    
    # Plan missing required 'token'
    plan = {
        "steps": [
            {"tool": action_name, "params": {"wrong": "data"}}
        ]
    }
    
    # 1. Test confirmation requirement (since it's a critical action)
    res = executor.execute_plan(plan, dry_run=False)
    assert res["status"] == "confirmation_required"
    proposal_id = res["proposal_id"]
    
    # 2. Test validation failure after confirmation
    executor.confirm(proposal_id, approved=True)
    res_val = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
    assert res_val["results"][0]["status"] == "validation_failed"
    
    # 3. Test successful execution with correct params
    plan_valid = {
        "steps": [
            {"tool": action_name, "params": {"token": "valid_token"}}
        ]
    }
    res_confirm = executor.execute_plan(plan_valid, dry_run=False)
    assert res_confirm["status"] == "confirmation_required"
    
    proposal_id_2 = res_confirm["proposal_id"]
    executor.confirm(proposal_id_2, approved=True)
    res_final = executor.execute_plan(plan_valid, dry_run=False, proposal_id=proposal_id_2)
    assert res_final["status"] == "ok"
    assert res_final["results"][0]["output"] == "secret_data"

def test_naming_convention_compliance():
    """Ensure all registered actions follow the DOMAIN.ENTITY.VERB pattern."""
    for name in action_registry._actions_by_name.keys():
        parts = name.split(".")
        # We expect DOMAIN.ENTITY.VERB or DOMAIN.ENTITY.VERB.MODIFIER
        assert len(parts) >= 3, f"Action name '{name}' does not follow DOMAIN.ENTITY.VERB hierarchy"
        assert all(p.isupper() for p in parts), f"Action name '{name}' must be all uppercase"
