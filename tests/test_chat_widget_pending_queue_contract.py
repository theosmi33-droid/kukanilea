from __future__ import annotations

from pathlib import Path

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


def _seed_dev_user(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)


def test_pending_queue_endpoint_returns_empty_list(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_dev_user(app)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    resp = client.get("/api/chat/compact?pending=1", headers={"X-CSRF-Token": "csrf-test"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["pending_approvals"] == []


def test_confirm_without_pending_id_returns_400(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_dev_user(app)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    resp = client.post(
        "/api/chat/compact",
        json={"confirm": True, "current_context": "/dashboard"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "Keine ausstehende Aktion" in body["text"]
