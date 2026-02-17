from __future__ import annotations

from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.actions import execute_action
from app.automation.store import create_rule, get_pending_action, get_rule


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


def test_automation_builder_requires_login() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.get("/automation", follow_redirects=False)
    assert res.status_code in {301, 302}
    assert "/login" in str(res.headers.get("Location") or "")


def test_automation_builder_toggle_rule(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Builder Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    client = app.test_client()
    _login(client)

    page = client.get("/automation")
    assert page.status_code == 200
    assert b"Automation Builder v1" in page.data

    res = client.post(
        f"/automation/{rule_id}/toggle",
        data={"enabled": "0"},
        follow_redirects=False,
    )
    assert res.status_code == 200
    rule = get_rule(tenant_id="KUKANILEA", rule_id=rule_id, db_path=db_path)
    assert rule is not None
    assert rule["is_enabled"] is False


def test_automation_pending_confirm_requires_ack_and_confirms(
    tmp_path: Path, monkeypatch
) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Builder Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    pending = execute_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "From pending",
            "requires_confirm": True,
        },
        context={"event_id": "42"},
        db_path=db_path,
        user_confirmed=False,
    )
    pending_id = str(pending.get("pending_id") or "")
    assert pending_id
    client = app.test_client()
    _login(client)

    blocked = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={},
        follow_redirects=False,
    )
    assert blocked.status_code == 400

    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 77)
    allowed = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1"},
        follow_redirects=False,
    )
    assert allowed.status_code == 200
    row = get_pending_action(
        tenant_id="KUKANILEA",
        pending_id=pending_id,
        db_path=db_path,
    )
    assert row is not None
    assert str(row.get("confirmed_at") or "").strip()
