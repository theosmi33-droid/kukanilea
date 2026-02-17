from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.runner import process_events_for_tenant
from app.automation.store import (
    create_rule,
    get_state_cursor,
    list_execution_logs,
)
from app.config import Config
from app.eventlog.core import event_append


def _set_core_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core, "DB_PATH", db_path)
    monkeypatch.setattr(Config, "CORE_DB", db_path)
    return db_path


def test_eventlog_trigger_matches_rule_and_updates_cursor(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="On Email",
        triggers=[
            {
                "trigger_type": "eventlog",
                "config": {"allowed_event_types": ["email.received"]},
            }
        ],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    event_id = event_append(
        "email.received",
        "mailbox_thread",
        1,
        {"tenant_id": "TENANT_A", "ref_id": "abc-1"},
    )

    result = process_events_for_tenant("TENANT_A", db_path=db_path)
    assert result["ok"] is True
    assert int(result["processed"]) >= 1
    assert int(result["matched"]) == 1
    assert str(result["cursor"]) == str(event_id)
    assert get_state_cursor(
        tenant_id="TENANT_A", source="eventlog", db_path=db_path
    ) == str(event_id)

    logs = list_execution_logs(tenant_id="TENANT_A", rule_id=rule_id, db_path=db_path)
    assert len(logs) == 1
    assert str(logs[0]["status"]) == "ok"
    assert str(logs[0]["trigger_ref"]) == f"eventlog:{event_id}"


def test_eventlog_trigger_ignores_non_matching_event_type(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    create_rule(
        tenant_id="TENANT_A",
        name="Only Lead Created",
        triggers=[
            {
                "trigger_type": "eventlog",
                "config": {"allowed_event_types": ["lead.created"]},
            }
        ],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    event_id = event_append(
        "email.received",
        "mailbox_thread",
        1,
        {"tenant_id": "TENANT_A", "ref_id": "abc-2"},
    )

    result = process_events_for_tenant("TENANT_A", db_path=db_path)
    assert result["ok"] is True
    assert int(result["processed"]) >= 1
    assert int(result["matched"]) == 0
    assert str(result["cursor"]) == str(event_id)
    logs = list_execution_logs(tenant_id="TENANT_A", db_path=db_path)
    assert logs == []


def test_eventlog_trigger_failure_keeps_cursor(monkeypatch, tmp_path: Path) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    create_rule(
        tenant_id="TENANT_A",
        name="Failing Rule",
        triggers=[
            {
                "trigger_type": "eventlog",
                "config": {"allowed_event_types": ["email.received"]},
            }
        ],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    event_append(
        "email.received",
        "mailbox_thread",
        1,
        {"tenant_id": "TENANT_A", "ref_id": "abc-3"},
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.automation.runner._process_rule_for_event", _raise)
    result = process_events_for_tenant("TENANT_A", db_path=db_path)
    assert result["ok"] is False
    assert str(result["reason"]) == "rule_processing_failed"
    assert (
        get_state_cursor(tenant_id="TENANT_A", source="eventlog", db_path=db_path) == ""
    )
