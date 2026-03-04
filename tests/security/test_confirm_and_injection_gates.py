from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _make_app(tmp_path: Path, monkeypatch):
    from app import create_app
    from app.auth import hash_password
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_user("bob", hash_password("bob"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
        auth_db.upsert_membership("bob", "KUKANILEA", "MITARBEITER", now)

    return app


def _auth_session(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


def test_write_routes_require_confirm_gate(monkeypatch, tmp_path: Path):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    _auth_session(client)

    response = client.post("/admin/settings/users/delete", data={"username": "bob"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "confirm_required"

    response = client.post(
        "/admin/settings/users/delete",
        data={"username": "bob", "confirm": "YES"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


def test_backup_restore_rejects_injection_pattern(monkeypatch, tmp_path: Path):
    from app.routes import admin_tenants

    app = _make_app(tmp_path, monkeypatch)
    _ = app

    malicious = "../../prod.db'; DROP TABLE users; --"
    try:
        admin_tenants._restore_backup(malicious)
        assert False, "expected invalid backup path"
    except ValueError as exc:
        assert str(exc) in {"backup_not_found", "invalid_backup_path"}
