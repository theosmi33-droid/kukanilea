from __future__ import annotations

import re
from pathlib import Path

from app.auth import hash_password
from app.web import validate_next
from tests.time_utils import utc_now_iso


def _make_app(tmp_path: Path, monkeypatch):
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


def test_validate_next_allows_root():
    assert validate_next("/") == "/"


def test_validate_next_allows_local_path_with_query():
    assert validate_next("/dashboard?tab=mail") == "/dashboard?tab=mail"


def test_validate_next_rejects_absolute_url():
    assert validate_next("https://evil.example/phish") == "/"


def test_validate_next_rejects_scheme_relative_url():
    assert validate_next("//evil.example/phish") == "/"


def test_validate_next_rejects_relative_path_without_slash():
    assert validate_next("dashboard") == "/"


def test_validate_next_rejects_javascript_scheme():
    assert validate_next("javascript:alert(1)") == "/"


def test_login_redirect_sanitizes_external_next(tmp_path: Path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()

    login_page = client.get("/login?next=https://evil.example/phish")
    assert login_page.status_code == 200
    html = login_page.get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert csrf, "csrf token not found on login page"

    resp = client.post(
        "/login?next=https://evil.example/phish",
        data={
            "username": "admin",
            "password": "adminpass",
            "csrf_token": csrf.group(1),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert "evil.example" not in location
    assert location == "/"


def test_login_route_has_limiter_decorator():
    source = Path("app/web.py").read_text(encoding="utf-8")
    assert "@login_limiter.limit_required" in source
