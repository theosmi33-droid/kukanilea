from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.auth import hash_password
from tests.time_utils import utc_now_iso


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


def _seed_admin(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("adminpass"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)


def _csrf_token(client):
    page = client.get("/login")
    html = page.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def test_dev_credentials_do_not_create_membership(app):
    _seed_admin(app)
    client = app.test_client()

    response = client.post(
        "/login",
        data={"username": "dev", "password": "dev", "csrf_token": _csrf_token(client)},
        follow_redirects=False,
    )
    assert response.status_code == 200

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        assert auth_db.get_memberships("dev") == []
