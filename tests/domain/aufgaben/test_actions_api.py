from __future__ import annotations

from tests.time_utils import utc_now_iso


def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True
    return app


def _auth_client(app, *, role="OPERATOR", username="operator"):

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user(username, hash_password(username), now)
        auth_db.upsert_membership(username, "KUKANILEA", role, now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = username
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"
    return client


def test_actions_list_exposes_schema(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/api/aufgaben/actions")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["tool"] in {"aufgaben", "tasks"}
    names = {item["name"] for item in data["actions"]}
    assert {"list", "create"}.issubset(names)


def test_actions_read_and_write_flow_with_approval_engine(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    read_response = client.post("/api/aufgaben/actions/list", json={"status": "OPEN"})
    assert read_response.status_code == 200
    read_json = read_response.get_json()
    assert read_json["ok"] is True
    assert read_json["name"] == "list"

    denied = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Neuer Task ohne Approval"},
    )
    assert denied.status_code == 409
    denied_json = denied.get_json()
    assert denied_json["error"] == "approval_required"
    approval_token = denied_json["approval"]["approval_token"]

    wrong_scope = client.post(
        "/api/aufgaben/actions/create",
        json={
            "title": "Anderer Task",
            "details": "scope mismatch",
            "approval_token": approval_token,
        },
    )
    assert wrong_scope.status_code == 409
    assert wrong_scope.get_json()["approval_reason"] == "scope_mismatch"

    expired_request = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Abgelaufener Task", "approval_ttl": 1},
    )
    assert expired_request.status_code == 409
    expired_token = expired_request.get_json()["approval"]["approval_token"]

    import time

    time.sleep(1.1)
    expired_use = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Abgelaufener Task", "approval_token": expired_token},
    )
    assert expired_use.status_code == 409
    assert expired_use.get_json()["approval_reason"] == "expired"

    challenge = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Neuer Task", "details": "via actions api"},
    )
    assert challenge.status_code == 409
    valid_token = challenge.get_json()["approval"]["approval_token"]

    created = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Neuer Task", "details": "via actions api", "approval_token": valid_token},
    )
    assert created.status_code == 200
    created_json = created.get_json()
    assert created_json["ok"] is True
    assert created_json["name"] == "create"

    after_read = client.post("/api/aufgaben/actions/list", json={"status": "OPEN"})
    assert after_read.status_code == 200
    items = after_read.get_json()["result"]["items"]
    assert any("Neuer Task" in str(item.get("title") or "") for item in items)


def test_actions_write_duplicate_request_returns_idempotent_replay(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    headers = {"Idempotency-Key": "dup-001"}
    first = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Mail Versand", "details": "kritisch", "confirm": "CONFIRM"},
        headers=headers,
    )
    second = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "Mail Versand", "details": "kritisch", "confirm": "CONFIRM"},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["idempotent_replay"] is True

    listed = client.post("/api/aufgaben/actions/list", json={"status": "OPEN"}).get_json()["result"]["items"]
    titles = [str(item.get("title") or "") for item in listed]
    assert titles.count("Mail Versand") == 1


def test_actions_retry_after_timeout_is_safe_and_repeatable(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    from app.web import TOOL_ACTION_TEMPLATES

    calls = {"count": 0}
    from app.modules.actions_api import ActionDefinition

    template = TOOL_ACTION_TEMPLATES["aufgaben"]
    original_action = template._actions["create"]

    def flaky(payload):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("simulated_timeout")
        return original_action.handler(payload)

    template._actions["create"] = ActionDefinition(
        name=original_action.name,
        title=original_action.title,
        permission=original_action.permission,
        risk=original_action.risk,
        input_schema=original_action.input_schema,
        output_schema=original_action.output_schema,
        handler=flaky,
    )
    try:
        headers = {"Idempotency-Key": "timeout-001"}
        first = client.post(
            "/api/aufgaben/actions/create",
            json={"title": "Kalender Sync", "confirm": "CONFIRM"},
            headers=headers,
        )
        second = client.post(
            "/api/aufgaben/actions/create",
            json={"title": "Kalender Sync", "confirm": "CONFIRM"},
            headers=headers,
        )
    finally:
        template._actions["create"] = original_action

    assert first.status_code == 500
    assert first.get_json()["error"] == "unexpected_error"
    assert second.status_code == 200
    assert second.get_json()["ok"] is True
    assert calls["count"] == 2


def test_actions_retry_after_approval_uses_same_idempotency_key(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    headers = {"Idempotency-Key": "approval-001"}
    denied = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "DMS Upload"},
        headers=headers,
    )
    approved = client.post(
        "/api/aufgaben/actions/create",
        json={"title": "DMS Upload", "confirm": "CONFIRM"},
        headers=headers,
    )

    assert denied.status_code == 409
    assert denied.get_json()["error"] == "approval_required"
    assert approved.status_code == 200
    assert approved.get_json()["ok"] is True


def test_actions_read_action_remains_unchanged_without_idempotency_contract(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.post("/api/aufgaben/actions/list", json={"status": "OPEN"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert "idempotent_replay" not in body


def test_settings_actions_list_exposes_setting_update_with_admin_permission(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/api/settings/actions")

    assert response.status_code == 200
    data = response.get_json()
    actions = {item["name"]: item for item in data["actions"]}
    assert "setting.read" in actions
    assert "setting.update" in actions
    assert actions["setting.update"]["permission"] == "admin"


def test_settings_setting_update_requires_admin_role(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    operator_client = _auth_client(app)

    denied = operator_client.post(
        "/api/settings/actions/setting.update",
        json={"key": "language", "value": "en"},
    )
    assert denied.status_code == 403


def test_settings_setting_update_admin_can_persist(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    admin_client = _auth_client(app, role="ADMIN", username="admin")

    approved = admin_client.post(
        "/api/settings/actions/setting.update",
        json={"key": "language", "value": "en"},
    )

    assert approved.status_code == 200
    body = approved.get_json()
    assert body["ok"] is True
    assert body["name"] == "setting.update"
    assert body["result"]["updated"] == "language"
    assert body["result"]["value"] == "en"

    with app.app_context():
        from app.routes.admin_tenants import _load_system_settings

        settings = _load_system_settings()
    assert settings["language"] == "en"
