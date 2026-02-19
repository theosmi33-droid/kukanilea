from __future__ import annotations

import re
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.store import get_rule, list_rules


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


def test_workflows_requires_login() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.get("/workflows", follow_redirects=False)
    assert res.status_code in {301, 302}
    assert "/login" in str(res.headers.get("Location") or "")


def test_workflow_template_install_is_idempotent(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    client = app.test_client()
    _login(client)

    page = client.get("/workflows")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)

    first = client.post(
        "/workflows/install/mail_followup_task",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert first.status_code == 302

    second = client.post(
        "/workflows/install/mail_followup_task",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert second.status_code == 302

    rows = list_rules(tenant_id="KUKANILEA", db_path=db_path)
    installed = [
        row
        for row in rows
        if "workflow_template:mail_followup_task" in str(row.get("description") or "")
    ]
    assert len(installed) == 1


def test_workflow_toggle_route_updates_enabled_flag(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    client = app.test_client()
    _login(client)

    page = client.get("/workflows")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)
    installed = client.post(
        "/workflows/install/invoice_document_review",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert installed.status_code == 302
    location = str(installed.headers.get("Location") or "")
    rule_id = location.rsplit("/", 1)[-1]
    assert rule_id

    enable = client.post(
        f"/workflows/{rule_id}/toggle",
        data={"csrf_token": csrf, "enabled": "1"},
        follow_redirects=False,
    )
    assert enable.status_code == 302

    rule = get_rule(tenant_id="KUKANILEA", rule_id=rule_id, db_path=db_path)
    assert rule is not None
    assert rule["is_enabled"] is True
