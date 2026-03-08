import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password
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


def _seed_admin(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("adminpass"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)


def _csrf_token(client):
    login_page = client.get("/login")
    assert login_page.status_code == 200
    html = login_page.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf token not found on login page"
    return match.group(1)


def test_dev_backdoor_credentials_are_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()

    resp = client.post(
        "/login",
        data={
            "username": "dev",
            "password": "dev",
            "csrf_token": _csrf_token(client),
        },
        follow_redirects=False,
    )

    assert resp.status_code == 200
    assert "Login fehlgeschlagen." in resp.get_data(as_text=True)

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        assert auth_db.get_user("dev") is None
