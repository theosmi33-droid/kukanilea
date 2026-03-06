from __future__ import annotations

from app.modules.automation.rules_engine import RulesEngine, RulesEngineState


def test_rules_engine_processes_yaml_trigger_and_actions() -> None:
    config = """
rules:
  - id: lead-onboarding
    trigger: new_lead
    retry:
      max_attempts: 2
    actions:
      - type: create_task
        payload:
          title: "Qualify lead"
      - type: notify
        payload:
          channel: "ops"
"""
    engine = RulesEngine.from_config_text(config)
    calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def executor(action_type: str, payload: dict[str, str], event: dict[str, str]) -> dict[str, bool]:
        calls.append((action_type, payload, event))
        return {"ok": True}

    result = engine.process_event({"id": "evt-1", "trigger": "new_lead"}, executor=executor)

    assert result["ok"] is True
    assert result["executed"] == 2
    assert result["failed"] == 0
    assert [entry[0] for entry in calls] == ["create_task", "notify"]


def test_rules_engine_retries_and_tracks_failure_then_success() -> None:
    config = """
[
  {
    "id": "invoice-reminder",
    "trigger": "overdue_invoice",
    "retry": {"max_attempts": 3},
    "actions": [{"type": "schedule_follow_up", "payload": {"days": 2}}]
  }
]
"""
    engine = RulesEngine.from_config_text(config)
    attempts = {"count": 0}

    def executor(action_type: str, payload: dict[str, int], event: dict[str, str]) -> dict[str, bool]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary_failure")
        return {"ok": True}

    result = engine.process_event(
        {"id": "evt-2", "trigger": "overdue_invoice"},
        executor=executor,
    )

    assert attempts["count"] == 3
    assert result["ok"] is True
    assert result["executed"] == 1
    assert result["failed"] == 0
    assert result["logs"][-1]["attempts"] == 3


def test_rules_engine_idempotency_skips_duplicates() -> None:
    engine = RulesEngine.from_config_text(
        """
        {
          "rules": [
            {
              "id": "message-chase",
              "trigger": "unanswered_message",
              "actions": [{"type": "create_draft", "payload": {"template": "nudge"}}]
            }
          ]
        }
        """
    )
    state = RulesEngineState()
    call_count = {"value": 0}

    def executor(action_type: str, payload: dict[str, str], event: dict[str, str]) -> dict[str, bool]:
        call_count["value"] += 1
        return {"ok": True}

    first = engine.process_event(
        {"id": "evt-3", "trigger": "unanswered_message"},
        executor=executor,
        state=state,
    )
    second = engine.process_event(
        {"id": "evt-3", "trigger": "unanswered_message"},
        executor=executor,
        state=state,
    )

    assert first["executed"] == 1
    assert second["executed"] == 0
    assert second["skipped"] == 1
    assert call_count["value"] == 1
    assert second["logs"][-1]["status"] == "skipped"
