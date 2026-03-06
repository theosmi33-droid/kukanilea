from app.core.action_executor import ActionExecutor
from app.core.agent_router import plan_actions


def test_chat_message_routes_to_confirmed_write_action_flow():
    calls = []

    def _write_tool(params):
        calls.append(params)
        return {"saved": True}

    executor = ActionExecutor({"core.write_action": _write_tool})
    plan = plan_actions("erstelle bericht für tenant alpha", {"tenant": "alpha", "user_id": "u-1"})

    proposal = executor.execute_plan(plan, dry_run=False)
    assert proposal["status"] == "confirmation_required"

    proposal_id = proposal["proposal_id"]
    assert executor.confirm(proposal_id, approved=True) is True

    response = executor.execute_plan(plan, dry_run=False, proposal_id=proposal_id)
    assert response["status"] == "ok"
    assert response["results"][0]["status"] == "executed"
    assert calls and calls[0]["tenant"] == "alpha"
