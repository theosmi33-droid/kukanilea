from __future__ import annotations

from app.modules.automation import actions


def test_execute_action_redacts_postfach_draft_content_in_pending_config(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    def _fake_create_pending_action(**kwargs):
        captured.update(kwargs)
        return "pending-1"

    monkeypatch.setattr(actions, "create_pending_action", _fake_create_pending_action)

    result = actions.execute_action(
        tenant_id="KUKANILEA",
        rule_id="rule-1",
        action_config={
            "action_type": "create_postfach_draft",
            "account_id": "acc-1",
            "to": "alice@example.com",
            "subject": "secret",
            "body": "top secret",
        },
        context={"thread_id": "th-1"},
        db_path=tmp_path / "core.sqlite3",
        user_confirmed=False,
    )

    assert result["status"] == "pending"
    pending_cfg = captured["action_config"]
    assert pending_cfg["action_type"] == "create_postfach_draft"
    assert pending_cfg["account_id"] == "acc-1"
    assert pending_cfg["sensitive_fields_redacted"] is True
    assert "to" not in pending_cfg
    assert "subject" not in pending_cfg
    assert "body" not in pending_cfg


def test_execute_action_keeps_non_postfach_pending_config_unchanged(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    def _fake_create_pending_action(**kwargs):
        captured.update(kwargs)
        return "pending-2"

    monkeypatch.setattr(actions, "create_pending_action", _fake_create_pending_action)

    result = actions.execute_action(
        tenant_id="KUKANILEA",
        rule_id="rule-2",
        action_config={"action_type": "create_task", "title": "Task A"},
        context={},
        db_path=tmp_path / "core.sqlite3",
        user_confirmed=False,
    )

    assert result["status"] == "pending"
    pending_cfg = captured["action_config"]
    assert pending_cfg == {"action_type": "create_task", "title": "Task A"}
