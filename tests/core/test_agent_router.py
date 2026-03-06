from app.core.agent_router import classify_intent, plan_actions


def test_classify_intent_detects_read_action():
    result = classify_intent("zeige status für tenant alpha")
    assert result["tool"] == "core.read_action"
    assert result["confidence"] >= 0.6

def test_classify_intent_detects_write_action_and_clarification():
    result = classify_intent("erstelle eine aufgabe")
    assert result["tool"] == "core.write_action"
    assert "Tenant".lower() in " ".join(result["needed_clarifications"]).lower()


def test_plan_actions_returns_clarification_step_for_ambiguous_input():
    plan = plan_actions("zeige und update projekt", {"tenant": "alpha"})
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["tool"] == "clarify.intent"
