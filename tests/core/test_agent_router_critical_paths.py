from __future__ import annotations

from app.core.agent_router import classify_intent, plan_actions


def test_classify_intent_empty_message_returns_clarification() -> None:
    result = classify_intent("", {"tenant_id": "KUKANILEA", "user_id": "qa"})
    assert result["tool"] == "clarify.intent"
    assert result["confidence"] == 0.0
    assert result["needed_clarifications"]


def test_classify_intent_high_risk_is_prioritized_over_read_write() -> None:
    result = classify_intent("zeige und update tenant alpha und purge alles")
    assert result["tool"] == "core.high_risk_action"
    assert result["confidence"] >= 0.9


def test_plan_actions_maps_high_risk_action_type() -> None:
    plan = plan_actions("shutdown tenant alpha", {"tenant": "alpha", "user_id": "qa"})
    assert plan["steps"][0]["tool"] == "core.high_risk_action"
    assert plan["steps"][0]["action_type"] == "high_risk"
