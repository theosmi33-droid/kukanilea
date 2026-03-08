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

    events = [row.get("event") for row in executor.audit_log]
    assert "propose" in events
    assert "confirm_requested" in events
    assert "confirm_granted" in events
    assert "execution_started" in events
    assert "execution_succeeded" in events
