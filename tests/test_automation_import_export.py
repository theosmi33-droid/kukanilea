from __future__ import annotations

import json
import re
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.store import create_rule, get_rule


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


def test_rule_export_and_safe_import(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    source_rule_id = create_rule(
        tenant_id="KUKANILEA",
        name="Export Source",
        description="safe export",
        max_executions_per_minute=7,
        triggers=[
            {
                "trigger_type": "eventlog",
                "config": {"allowed_event_types": ["lead.created"]},
            }
        ],
        conditions=[],
        actions=[{"action_type": "create_task", "config": {"requires_confirm": False}}],
        db_path=db_path,
    )

    client = app.test_client()
    _login(client)

    exported = client.get(f"/automation/{source_rule_id}/export")
    assert exported.status_code == 200
    body = exported.get_json() or {}
    item = body.get("item") or {}
    assert item.get("name") == "Export Source"
    assert int(item.get("max_executions_per_minute") or 0) == 7

    page = client.get("/automation")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)

    invalid = dict(item)
    invalid["unexpected"] = "x"
    invalid_response = client.post(
        "/automation/import",
        data={"csrf_token": csrf, "rule_json": json.dumps(invalid)},
        follow_redirects=False,
    )
    assert invalid_response.status_code == 400

    valid_response = client.post(
        "/automation/import",
        data={"csrf_token": csrf, "rule_json": json.dumps(item)},
        follow_redirects=False,
    )
    assert valid_response.status_code == 200
    imported_body = valid_response.get_json() or {}
    imported_rule_id = str(imported_body.get("rule_id") or "")
    assert imported_rule_id

    imported = get_rule(
        tenant_id="KUKANILEA",
        rule_id=imported_rule_id,
        db_path=db_path,
    )
    assert imported is not None
    assert imported["name"] == "Export Source"
    assert imported["is_enabled"] is False
    assert int(imported["max_executions_per_minute"]) == 7


def test_rule_import_supports_cron_and_email_draft(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    client = app.test_client()
    _login(client)
    page = client.get("/automation")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)

    payload = {
        "name": "Cron Draft Rule",
        "description": "phase 3.3",
        "max_executions_per_minute": 5,
        "triggers": [{"trigger_type": "cron", "config": {"cron": "0 8 * * 1"}}],
        "conditions": [],
        "actions": [
            {
                "action_type": "email_draft",
                "config": {
                    "to": ["kunde@example.com"],
                    "subject": "Weekly",
                    "body_template": "Hallo",
                },
            }
        ],
    }
    response = client.post(
        "/automation/import",
        data={"csrf_token": csrf, "rule_json": json.dumps(payload)},
        follow_redirects=False,
    )
    assert response.status_code == 200
    body = response.get_json() or {}
    rule_id = str(body.get("rule_id") or "")
    assert rule_id
    imported = get_rule(tenant_id="KUKANILEA", rule_id=rule_id, db_path=db_path)
    assert imported is not None
    assert any(str(t.get("type") or "") == "cron" for t in imported["triggers"])
    assert any(str(a.get("type") or "") == "email_draft" for a in imported["actions"])


def test_rule_import_rejects_invalid_cron_expression(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    _set_core_db(tmp_path)
    client = app.test_client()
    _login(client)
    page = client.get("/automation")
    assert page.status_code == 200
    csrf = _csrf_from_html(page.data)
    payload = {
        "name": "Invalid cron",
        "description": "",
        "max_executions_per_minute": 5,
        "triggers": [{"trigger_type": "cron", "config": {"cron": "*/15 8 * * *"}}],
        "conditions": [],
        "actions": [],
    }
    response = client.post(
        "/automation/import",
        data={"csrf_token": csrf, "rule_json": json.dumps(payload)},
        follow_redirects=False,
    )
    assert response.status_code == 400
