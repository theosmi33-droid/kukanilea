import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password


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
        now = datetime.utcnow().isoformat()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("adminpass"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)


def _login(client):
    login_page = client.get("/login")
    assert login_page.status_code == 200
    html = login_page.get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert csrf, "csrf token not found on login page"

    resp = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "adminpass",
            "csrf_token": csrf.group(1),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_projects_route_returns_200_for_authenticated_user(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()

    _login(client)

    resp = client.get("/projects", follow_redirects=False)
    assert resp.status_code == 200
    assert "kanban" in resp.get_data(as_text=True).lower()


def test_projects_hx_partial_returns_200(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()

    _login(client)

    resp = client.get("/projects", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "Projektboard wird geladen" in resp.get_data(as_text=True)
