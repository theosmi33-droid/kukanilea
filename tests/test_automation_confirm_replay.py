from __future__ import annotations

import re
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
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        payload,
    )
    assert match is not None
    return match.group(1).decode("utf-8")


def _create_pending(db_path: Path, monkeypatch) -> str:
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Replay Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 501)
    pending = execute_action(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        action_config={
            "action_type": "create_task",
            "title": "Replay Task",
            "requires_confirm": True,
        },
        context={"event_id": "777"},
        db_path=db_path,
        user_confirmed=False,
    )
    pending_id = str(pending.get("pending_id") or "")
    assert pending_id
    return pending_id


def test_confirm_with_valid_token_succeeds(tmp_path: Path, monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    pending_id = _create_pending(db_path, monkeypatch)
    row = get_pending_action(
        tenant_id="KUKANILEA", pending_id=pending_id, db_path=db_path
    )
    assert row is not None
    token = str(row.get("confirm_token") or "")

    client = app.test_client()
    _login(client)
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    csrf = _csrf_from_html(pending_page.data)
    res = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1", "confirm_token": token, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert res.status_code == 200


def test_confirm_replay_with_same_token_blocked(tmp_path: Path, monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    pending_id = _create_pending(db_path, monkeypatch)
    row = get_pending_action(
        tenant_id="KUKANILEA", pending_id=pending_id, db_path=db_path
    )
    assert row is not None
    token = str(row.get("confirm_token") or "")

    client = app.test_client()
    _login(client)
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    csrf = _csrf_from_html(pending_page.data)
    first = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1", "confirm_token": token, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert first.status_code == 200
    second = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1", "confirm_token": token, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert second.status_code == 403


def test_confirm_with_wrong_token_fails(tmp_path: Path, monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    pending_id = _create_pending(db_path, monkeypatch)

    client = app.test_client()
    _login(client)
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    csrf = _csrf_from_html(pending_page.data)
    res = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1", "confirm_token": "wrong-token", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert res.status_code == 403


def test_confirm_without_token_fails(tmp_path: Path, monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    pending_id = _create_pending(db_path, monkeypatch)

    client = app.test_client()
    _login(client)
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    csrf = _csrf_from_html(pending_page.data)
    res = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert res.status_code == 400
