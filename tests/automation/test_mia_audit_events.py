from __future__ import annotations

import sqlite3

from app.config import Config
from app.modules.automation.store import (
    append_execution_log,
    confirm_pending_action_once,
    create_rule,
    create_pending_action,
    ensure_automation_schema,
    update_execution_log,
    update_pending_action_status,
)


def _count_event(db_path, event_type: str) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT COUNT(1) FROM events WHERE event_type=?", (event_type,)).fetchone()
        return int((row[0] if row else 0) or 0)
    finally:
        con.close()


def test_pending_action_emits_mia_proposal_and_confirm(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    Config.CORE_DB = str(db_path)
    ensure_automation_schema(db_path)
    rule_id = create_rule(tenant_id="KUKANILEA", name="rule-1", db_path=db_path)

    pending_id = create_pending_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        action_type="create_task",
        action_config={"title": "x"},
        context_snapshot={"source": "test"},
        confirm_token="abc",
        db_path=db_path,
    )
    assert pending_id
    assert _count_event(db_path, "mia.proposal.created") == 1
    assert _count_event(db_path, "mia.confirm.requested") == 1


def test_pending_confirm_and_expired_emit_mia_events(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    Config.CORE_DB = str(db_path)
    ensure_automation_schema(db_path)
    rule_id = create_rule(tenant_id="KUKANILEA", name="rule-2", db_path=db_path)
    rule_id_2 = create_rule(tenant_id="KUKANILEA", name="rule-3", db_path=db_path)

    pending_id = create_pending_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        action_type="create_task",
        action_config={"title": "x"},
        context_snapshot={"source": "test"},
        confirm_token="xyz",
        db_path=db_path,
    )
    row = confirm_pending_action_once(
        tenant_id="KUKANILEA",
        pending_id=pending_id,
        confirm_token="xyz",
        db_path=db_path,
    )
    assert row is not None
    assert _count_event(db_path, "mia.confirm.granted") == 1

    pending_id_2 = create_pending_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id_2,
        action_type="create_task",
        action_config={"title": "y"},
        context_snapshot={"source": "test"},
        confirm_token="def",
        db_path=db_path,
    )
    assert update_pending_action_status(
        tenant_id="KUKANILEA",
        pending_id=pending_id_2,
        status="failed",
        db_path=db_path,
    )
    assert _count_event(db_path, "mia.confirm.expired") == 1


def test_execution_log_updates_emit_mia_execution_events(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    Config.CORE_DB = str(db_path)
    ensure_automation_schema(db_path)
    rule_id = create_rule(tenant_id="KUKANILEA", name="rule-4", db_path=db_path)
    rule_id_2 = create_rule(tenant_id="KUKANILEA", name="rule-5", db_path=db_path)

    appended = append_execution_log(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        trigger_type="event",
        trigger_ref="evt-1",
        status="started",
        db_path=db_path,
    )
    assert appended["ok"] is True
    log_id = appended["log_id"]
    assert log_id

    assert update_execution_log(
        tenant_id="KUKANILEA",
        log_id=log_id,
        status="ok",
        output_redacted="done",
        db_path=db_path,
    )
    assert _count_event(db_path, "mia.execution.started") >= 1
    assert _count_event(db_path, "mia.execution.finished") == 1
    assert _count_event(db_path, "mia.audit_trail.linked") == 1

    appended2 = append_execution_log(
        tenant_id="KUKANILEA",
        rule_id=rule_id_2,
        trigger_type="event",
        trigger_ref="evt-2",
        status="started",
        db_path=db_path,
    )
    assert update_execution_log(
        tenant_id="KUKANILEA",
        log_id=appended2["log_id"],
        status="failed",
        error_redacted="err",
        db_path=db_path,
    )
    assert _count_event(db_path, "mia.execution.failed") == 1
