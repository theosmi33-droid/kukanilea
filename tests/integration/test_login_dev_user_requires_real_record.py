from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.auth import hash_password
from tests.time_utils import utc_now_iso


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app
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
        auth_db.upsert_user("dev", hash_password("secure-dev-pass"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    return app.test_client()


def _csrf(client):
    page = client.get("/login")
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))
    assert match
    return match.group(1)


def test_dev_user_requires_db_password_not_literal_dev(client):
    denied = client.post(
        "/login",
        data={"username": "dev", "password": "dev", "csrf_token": _csrf(client)},
        follow_redirects=False,
    )
    assert denied.status_code == 200
    assert "Login fehlgeschlagen." in denied.get_data(as_text=True)

    allowed = client.post(
        "/login",
        data={"username": "dev", "password": "secure-dev-pass", "csrf_token": _csrf(client)},
        follow_redirects=False,
    )
    assert allowed.status_code == 302
