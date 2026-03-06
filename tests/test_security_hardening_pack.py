from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    monkeypatch.setattr(Config, "CORS_ALLOWED_ORIGINS", ["https://allowed.example"])
    app = create_app()
    app.config["TESTING"] = True
    return app


def _seed_admin(app):
    from tests.time_utils import utc_now_iso
    from app.auth import hash_password

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)


def _login_session(client):
    now = time.time()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["last_active"] = now
        sess["issued_at"] = now
        sess["csrf_token"] = "test-csrf"


def test_cors_blocks_disallowed_origin(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/api/ping", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload["error"]["code"] == "cors_blocked"


def test_protected_api_requires_valid_membership(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()
    _login_session(client)

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        with auth_db._db() as con:
            con.execute("DELETE FROM memberships WHERE username = ?", ("admin",))
            con.commit()

    response = client.get("/api/outbound/status")
    assert response.status_code == 403


def test_outbound_status_does_not_leak_raw_errors(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()
    _login_session(client)

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        with auth_db._db() as con:
            con.execute("DROP TABLE IF EXISTS api_outbound_queue")
            con.commit()

    response = client.get("/api/outbound/status")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"] == "internal_error"
    assert "no such table" not in response.get_data(as_text=True)


def test_session_absolute_timeout_enforced(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    app.config["SESSION_ABSOLUTE_TIMEOUT_SECONDS"] = 1
    client = app.test_client()

    stale = time.time() - 10
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["last_active"] = stale
        sess["issued_at"] = stale

    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")
