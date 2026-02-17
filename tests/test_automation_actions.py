from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.actions import execute_action, run_rule_actions
from app.automation.store import create_rule, list_pending_actions


def _set_core_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core, "DB_PATH", db_path)
    return db_path


def test_automation_action_unknown_fails(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    outcome = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={"action_type": "email.send"},
        context={"event_id": "1"},
        db_path=db_path,
    )
    assert outcome["status"] == "failed"
    assert outcome["error"] == "action_not_allowed"


def test_automation_action_create_task_direct_when_confirm_not_required(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 1234)
    outcome = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "Followup",
            "requires_confirm": False,
        },
        context={"event_id": "5", "trigger_ref": "eventlog:5"},
        db_path=db_path,
    )
    assert outcome["status"] == "ok"
    assert int(outcome["result"]["task_id"]) == 1234
    assert list_pending_actions(tenant_id="TENANT_A", db_path=db_path) == []


def test_automation_action_create_postfach_draft_always_pending(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    outcome = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "create_postfach_draft",
            "requires_confirm": False,
            "account_id": "acc-1",
            "to": "x@example.com",
            "subject": "Hi",
            "body": "Body",
        },
        context={"event_id": "9"},
        db_path=db_path,
    )
    assert outcome["status"] == "pending"
    pending = list_pending_actions(tenant_id="TENANT_A", db_path=db_path)
    assert len(pending) == 1
    assert str(pending[0]["action_type"]) == "create_postfach_draft"


def test_automation_action_confirm_gate_enforced(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 88)

    blocked = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "Task",
            "requires_confirm": True,
        },
        context={"event_id": "10"},
        db_path=db_path,
        user_confirmed=False,
    )
    assert blocked["status"] == "pending"

    allowed = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "Task",
            "requires_confirm": True,
        },
        context={"event_id": "10"},
        db_path=db_path,
        user_confirmed=True,
    )
    assert allowed["status"] == "ok"


def test_automation_run_rule_actions_summary(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 999)
    result = run_rule_actions(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        actions=[
            {"action_type": "create_task", "title": "A", "requires_confirm": False},
            {"action_type": "create_postfach_draft", "account_id": "acc-1"},
            {"action_type": "invalid"},
        ],
        context={"event_id": "11"},
        db_path=db_path,
    )
    assert result["ok"] is False
    assert int(result["executed"]) == 1
    assert int(result["pending"]) == 1
    assert int(result["failed"]) == 1
