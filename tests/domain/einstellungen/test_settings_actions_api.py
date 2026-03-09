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


def _auth_client(app, *, role: str = "OPERATOR", username: str = "operator"):
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


def test_settings_actions_list_exposes_parity_actions(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/api/settings/actions")

    assert response.status_code == 200
    payload = response.get_json()
    actions = {item["name"]: item for item in payload["actions"]}
    assert {"setting.read", "setting.update", "key.rotate"}.issubset(actions.keys())
    assert actions["setting.read"]["confirm_required"] is False
    assert actions["setting.update"]["permission"] == "admin"
    assert actions["setting.update"]["confirm_required"] is False
    assert actions["key.rotate"]["confirm_required"] is True


def test_settings_read_action_returns_expected_contract_payload(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.post("/api/settings/actions/setting.read", json={})

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["name"] == "setting.read"
    result = body["result"]
    assert result["security_headers"] == "active"
    assert result["actions"] == ["setting.read", "setting.update", "key.rotate"]


def test_settings_update_action_requires_admin_role(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app, role="OPERATOR", username="operator")

    denied = client.post(
        "/api/settings/actions/setting.update",
        json={"scope": "tenant", "key": "ui.theme", "value": "dark"},
    )
    assert denied.status_code == 403


def test_settings_update_action_admin_succeeds_without_confirm(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app, role="ADMIN", username="admin")

    approved = client.post(
        "/api/settings/actions/setting.update",
        json={"scope": "tenant", "key": "ui.theme", "value": "dark"},
    )
    assert approved.status_code == 200
    result = approved.get_json()["result"]
    assert result["updated"] is True
    assert result["key"] == "ui.theme"
    assert result["scope"] == "tenant"


def test_settings_rotate_action_is_approval_gated_and_blocked_placeholder(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    denied = client.post("/api/settings/actions/key.rotate", json={"key_name": "mesh-signing-key"})
    assert denied.status_code == 409
    assert denied.get_json()["error"] == "approval_required"

    approved = client.post(
        "/api/settings/actions/key.rotate",
        json={"key_name": "mesh-signing-key", "confirm": "CONFIRM"},
    )
    assert approved.status_code == 200
    result = approved.get_json()["result"]
    assert result["blocked"] is True
    assert result["rotation_available"] is False
    assert result["next_step"] == "manual_runbook_required"


def test_settings_actions_enforce_session_tenant_in_handler_payload(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    from app.modules.actions_api import ActionDefinition
    from app.web import TOOL_ACTION_TEMPLATES

    template = TOOL_ACTION_TEMPLATES["settings"]
    original_action = template._actions["setting.read"]
    seen: dict[str, str | None] = {"tenant_id": None}

    def _capture(payload):
        seen["tenant_id"] = str(payload.get("tenant_id") or "")
        return {"tenant_id": seen["tenant_id"], "actions": []}

    template._actions["setting.read"] = ActionDefinition(
        name=original_action.name,
        title=original_action.title,
        permission=original_action.permission,
        risk=original_action.risk,
        input_schema=original_action.input_schema,
        output_schema=original_action.output_schema,
        handler=_capture,
    )

    try:
        response = client.post("/api/settings/actions/setting.read", json={"tenant_id": "VICTIM"})
    finally:
        template._actions["setting.read"] = original_action

    assert response.status_code == 200
    assert seen["tenant_id"] == "KUKANILEA"
