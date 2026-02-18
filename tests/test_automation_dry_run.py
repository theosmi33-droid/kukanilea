from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.store import create_rule, list_execution_logs, list_pending_actions


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


def _set_core_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.sqlite3"
    webmod.core.DB_PATH = db_path
    core.DB_PATH = db_path
    return db_path


def _csrf_from_html(payload: bytes) -> str:
    match = re.search(rb'name="csrf_token"\s+value="([^"]+)"', payload)
    assert match is not None
    return match.group(1).decode("utf-8")


def test_rule_simulation_creates_log_without_pending_actions(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Dry run rule",
        triggers=[
            {
                "trigger_type": "eventlog",
                "config": {"allowed_event_types": ["email.received"]},
            }
        ],
        conditions=[],
        actions=[
            {
                "action_type": "create_task",
                "config": {"title": "dry run", "requires_confirm": False},
            }
        ],
        db_path=db_path,
    )
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY,
              ts TEXT NOT NULL,
              event_type TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id INTEGER NOT NULL,
              payload_json TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            INSERT INTO events(id, ts, event_type, entity_type, entity_id, payload_json)
            VALUES (1,'2026-02-18T10:00:00Z','email.received','mailbox_thread',1,'{\"tenant_id\":\"KUKANILEA\",\"ref_id\":\"dry-1\"}')
            """
        )
        con.commit()
    finally:
        con.close()
    event_id = 1

    client = app.test_client()
    _login(client)
    detail = client.get(f"/automation/{rule_id}")
    assert detail.status_code == 200
    csrf = _csrf_from_html(detail.data)

    response = client.post(
        f"/automation/{rule_id}/simulate",
        data={"csrf_token": csrf, "event_id": str(event_id)},
        follow_redirects=False,
    )
    assert response.status_code == 200
    body = response.get_json() or {}
    assert body.get("ok") is True
    result = body.get("result") or {}
    assert str(result.get("event_id") or "") == str(event_id)

    logs = list_execution_logs(tenant_id="KUKANILEA", rule_id=rule_id, db_path=db_path)
    assert any(str(row.get("trigger_type") or "") == "simulation" for row in logs)
    assert list_pending_actions(tenant_id="KUKANILEA", db_path=db_path) == []
