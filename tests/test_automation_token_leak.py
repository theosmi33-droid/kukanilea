from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.actions import execute_action
from app.automation.store import create_rule, get_pending_action


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


def test_pending_token_not_exposed_in_query_or_eventlog(
    tmp_path: Path, monkeypatch
) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Token leak rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 901)
    pending = execute_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "secure confirm",
            "requires_confirm": True,
        },
        context={"event_id": "9"},
        db_path=db_path,
        user_confirmed=False,
    )
    pending_id = str(pending.get("pending_id") or "")
    row = get_pending_action(
        tenant_id="KUKANILEA", pending_id=pending_id, db_path=db_path
    )
    assert row is not None
    token = str(row.get("confirm_token") or "")
    assert token

    client = app.test_client()
    _login(client)
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    html = pending_page.data.decode("utf-8", errors="ignore")
    assert "?confirm_token=" not in html
    assert f'name="confirm_token" value="{token}"' in html
    for comment in re.findall(r"<!--(.*?)-->", html, flags=re.S):
        assert token not in comment

    csrf = _csrf_from_html(pending_page.data)
    confirm = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"csrf_token": csrf, "safety_ack": "1", "confirm_token": token},
        follow_redirects=False,
    )
    assert confirm.status_code == 200

    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events' LIMIT 1"
        ).fetchone()
        if exists:
            rows = con.execute("SELECT payload_json FROM events").fetchall()
            payloads = " ".join(str(row["payload_json"] or "") for row in rows)
            assert token not in payloads
    finally:
        con.close()
