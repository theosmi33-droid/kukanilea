from __future__ import annotations

import re
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


def _csrf_from_html(payload: bytes) -> str:
    match = re.search(
        rb'name="csrf_token"\s+value="([^"]+)"',
        payload,
    )
    assert match is not None
    return match.group(1).decode("utf-8")


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
    csrf = _csrf_from_html(page.data)

    res = client.post(
        f"/automation/{rule_id}/toggle",
        data={"enabled": "0", "csrf_token": csrf},
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
    pending_page = client.get("/automation/pending")
    assert pending_page.status_code == 200
    csrf = _csrf_from_html(pending_page.data)

    blocked = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert blocked.status_code == 400

    monkeypatch.setattr(core, "task_create", lambda **_kwargs: 77)
    row_before = get_pending_action(
        tenant_id="KUKANILEA",
        pending_id=pending_id,
        db_path=db_path,
    )
    assert row_before is not None
    token = str(row_before.get("confirm_token") or "")
    assert token
    allowed = client.post(
        f"/automation/pending/{pending_id}/confirm",
        data={"safety_ack": "1", "confirm_token": token, "csrf_token": csrf},
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


def test_automation_rule_detail_supports_cron_and_mail_actions(
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
    client = app.test_client()
    _login(client)
    monkeypatch.setattr(
        webmod.Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", ["hooks.example.com"]
    )
    detail = client.get(f"/automation/{rule_id}")
    assert detail.status_code == 200
    assert b"cron_expression" in detail.data
    assert b"body_template" in detail.data
    assert b"/action/email-send" in detail.data
    assert b"/action/webhook" in detail.data
    csrf = _csrf_from_html(detail.data)

    add_cron = client.post(
        f"/automation/{rule_id}/trigger/cron",
        data={"csrf_token": csrf, "cron_expression": "0 8 * * 1"},
        follow_redirects=False,
    )
    assert add_cron.status_code == 302

    add_action = client.post(
        f"/automation/{rule_id}/action/email-draft",
        data={
            "csrf_token": csrf,
            "to": "kunde@example.com",
            "subject": "Wochenreport",
            "body_template": "Hallo {customer_name}",
        },
        follow_redirects=False,
    )
    assert add_action.status_code == 302

    add_send_action = client.post(
        f"/automation/{rule_id}/action/email-send",
        data={
            "csrf_token": csrf,
            "to": "kunde@example.com",
            "subject": "Jetzt senden",
            "body_template": "Hallo {customer_name}",
        },
        follow_redirects=False,
    )
    assert add_send_action.status_code == 302

    add_webhook_action = client.post(
        f"/automation/{rule_id}/action/webhook",
        data={
            "csrf_token": csrf,
            "url": "https://hooks.example.com/hook",
            "method": "POST",
            "body_template": '{"event":"{{event_type}}"}',
            "headers_json": '{"X-Source":"kukanilea"}',
        },
        follow_redirects=False,
    )
    assert add_webhook_action.status_code == 302

    rule = get_rule(tenant_id="KUKANILEA", rule_id=rule_id, db_path=db_path)
    assert rule is not None
    assert any(str(t.get("type") or "") == "cron" for t in rule["triggers"])
    assert any(str(a.get("type") or "") == "email_draft" for a in rule["actions"])
    assert any(str(a.get("type") or "") == "email_send" for a in rule["actions"])
    assert any(str(a.get("type") or "") == "webhook" for a in rule["actions"])
