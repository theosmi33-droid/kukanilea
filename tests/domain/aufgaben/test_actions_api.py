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


def test_actions_list_exposes_schema(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/api/aufgaben/actions")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["tool"] == "aufgaben"
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
