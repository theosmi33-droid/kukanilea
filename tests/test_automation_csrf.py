from __future__ import annotations

import re
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.store import create_rule


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


def test_automation_post_without_csrf_is_forbidden(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="CSRF Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    client = app.test_client()
    _login(client)

    response = client.post(
        f"/automation/{rule_id}/toggle",
        data={"enabled": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_automation_post_with_invalid_csrf_is_forbidden(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="CSRF Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    client = app.test_client()
    _login(client)
    page = client.get("/automation")
    assert page.status_code == 200

    response = client.post(
        f"/automation/{rule_id}/toggle",
        data={"enabled": "0", "csrf_token": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_automation_post_with_valid_csrf_is_allowed(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="CSRF Rule",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    client = app.test_client()
    _login(client)
    page = client.get("/automation")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)

    response = client.post(
        f"/automation/{rule_id}/toggle",
        data={"enabled": "0", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 200
