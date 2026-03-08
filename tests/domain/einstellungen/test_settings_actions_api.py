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


def _auth_client(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("operator", hash_password("operator"), now)
        auth_db.upsert_membership("operator", "KUKANILEA", "OPERATOR", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "operator"
        sess["role"] = "OPERATOR"
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
    assert actions["setting.update"]["confirm_required"] is True
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


def test_settings_update_action_requires_confirm_then_succeeds(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    denied = client.post(
        "/api/settings/actions/setting.update",
        json={"scope": "tenant", "key": "ui.theme", "value": "dark"},
    )
    assert denied.status_code == 409
    assert denied.get_json()["error"] == "approval_required"

    approved = client.post(
        "/api/settings/actions/setting.update",
        json={"scope": "tenant", "key": "ui.theme", "value": "dark", "confirm": "CONFIRM"},
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
