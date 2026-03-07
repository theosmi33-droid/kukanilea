from __future__ import annotations

from pathlib import Path

from tests.time_utils import utc_now_iso


def _app(tmp_path: Path, monkeypatch):
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
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    return app


def test_post_blocked_when_read_only(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    app.config["READ_ONLY"] = True
    app.config["LICENSE_REASON"] = "license_blocked"
    client = app.test_client()
    resp = client.post("/api/does-not-exist", json={"x": 1})
    assert resp.status_code == 403
    assert "read_only" in resp.get_data(as_text=True)


def test_get_allowed_when_read_only(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    app.config["READ_ONLY"] = True
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code in {200, 404}


def test_license_upload_endpoint_not_blocked(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    app.config["READ_ONLY"] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    resp = client.post("/admin/license")
    assert resp.status_code != 403


def test_non_license_settings_write_blocked_in_read_only(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch)
    app.config["READ_ONLY"] = True
    app.config["LICENSE_REASON"] = "grace_read_only"
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.post(
        "/admin/settings/system",
        data={
            "language": "de",
            "timezone": "Europe/Berlin",
            "backup_interval": "daily",
            "log_level": "INFO",
            "confirm": "YES",
        },
    )
    assert resp.status_code == 403
    assert "read_only" in resp.get_data(as_text=True)
