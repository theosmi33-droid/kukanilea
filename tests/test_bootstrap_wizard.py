import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest


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


def test_fresh_db_redirects_to_bootstrap(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/bootstrap" in (resp.headers.get("Location") or "")


def test_bootstrap_non_localhost_forbidden(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/bootstrap", environ_base={"REMOTE_ADDR": "8.8.8.8"})
    assert resp.status_code == 403


def test_bootstrap_post_creates_dev_user_and_shows_credentials(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.post(
        "/bootstrap",
        data={
            "tenant_name": "KUKANILEA",
            "admin_user": "devseed",
            "admin_pass": "devseed-pass",
        },
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Bootstrap abgeschlossen" in body
    assert "devseed" in body
    assert "devseed-pass" in body

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        assert auth_db.count_users() >= 1
        assert auth_db.get_user("devseed") is not None
