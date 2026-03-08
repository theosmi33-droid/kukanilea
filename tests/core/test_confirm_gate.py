from app.core.action_executor import ActionExecutor


def test_write_plan_requires_confirmation_before_execution():
    executor = ActionExecutor({"core.write_action": lambda params: {"ok": True, "params": params}})
    plan = {
        "steps": [
            {"tool": "core.write_action", "action_type": "write", "params": {"tenant": "alpha"}},
        ]
    }

    response = executor.execute_plan(plan, dry_run=False)
    assert response["status"] == "confirmation_required"
    assert response["proposal_id"].startswith("proposal-")


def test_confirm_protocol_executes_after_approval_and_writes_audit_log():
    executor = ActionExecutor({"core.write_action": lambda params: {"ok": True, "tenant": params.get("tenant")}})
    plan = {
        "steps": [
            {"tool": "core.write_action", "action_type": "write", "params": {"tenant": "alpha"}},
        ]
    }

    proposed = executor.execute_plan(plan, dry_run=False)
    proposal_id = proposed["proposal_id"]
    assert executor.confirm(proposal_id, approved=True) is True

    executed = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
    assert executed["status"] == "ok"
    assert executed["results"][0]["status"] == "executed"

    statuses = [row["status"] for row in executor.audit_log]
    assert "awaiting_confirmation" in statuses
    assert "executed" in statuses


def test_confirmed_proposal_rejects_plan_substitution():
    executed_params = []

    def write_tool(params):
        executed_params.append(params)
        return {"ok": True}

    executor = ActionExecutor({"core.write_action": write_tool})
    approved_plan = {
        "steps": [
            {"tool": "core.write_action", "action_type": "write", "params": {"tenant": "alpha"}},
        ]
    }
    substituted_plan = {
        "steps": [
            {"tool": "core.write_action", "action_type": "write", "params": {"tenant": "beta"}},
        ]
    }

    proposed = executor.execute_plan(approved_plan, dry_run=False)
    proposal_id = proposed["proposal_id"]
    assert executor.confirm(proposal_id, approved=True) is True

    mismatch = executor.execute_plan(substituted_plan, dry_run=False, proposal_id=proposal_id)
    assert mismatch == {"status": "plan_mismatch", "proposal_id": proposal_id}
    assert executed_params == []

    executed = executor.execute_plan(approved_plan, dry_run=False, proposal_id=proposal_id)
    assert executed["status"] == "ok"
    assert executed_params == [{"tenant": "alpha"}]
