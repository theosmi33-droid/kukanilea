from __future__ import annotations

import re
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.actions import execute_action
from app.automation.store import create_rule, get_pending_action


def _login(client, role: str) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
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


def test_pending_confirm_requires_admin_or_dev_role(
    tmp_path: Path, monkeypatch
) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Role gate rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 900)
    pending = execute_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "restricted",
            "requires_confirm": True,
        },
        context={"event_id": "1"},
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
    _login(client, role="OPERATOR")
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    csrf = _csrf_from_html(pending_page.data)

    response = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"csrf_token": csrf, "safety_ack": "1", "confirm_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 403

    still_pending = get_pending_action(
        tenant_id="KUKANILEA", pending_id=pending_id, db_path=db_path
    )
    assert still_pending is not None
    assert str(still_pending.get("status") or "") == "pending"
