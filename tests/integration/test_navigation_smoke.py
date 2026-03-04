from __future__ import annotations

from tests.time_utils import utc_now_iso

import re


HTMX_PATHS = [
    "/dashboard",
    "/upload",
    "/projects",
    "/tasks",
    "/messenger",
    "/email",
    "/calendar",
    "/time",
    "/visualizer",
    "/settings",
    "/assistant",
]


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


def _auth_client(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    return client


def test_main_navigation_and_main_paths(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    root = client.get("/", follow_redirects=True)
    html = root.get_data(as_text=True)
    assert root.status_code == 200

    for nav_path in HTMX_PATHS:
        assert f'href="{nav_path}"' in html

    # Main sidebar navigation is full-page by design (no sidebar htmx partial attributes).
    assert not re.search(r'<a[^>]+data-route="[^"]+"[^>]+hx-get=', html)

    for path in HTMX_PATHS:
        response = client.get(path, headers={"HX-Request": "true"})
        assert response.status_code == 200, f"HTMX path failed: {path}"
        body = response.get_data(as_text=True)
        assert "traceback" not in body.lower(), f"Error page returned for {path}"
        assert "Internal Server Error" not in body
        assert "wird geladen" not in body.lower(), f"Loading placeholder returned for {path}"


def test_dashboard_contract_matrix_has_11_tiles(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/api/dashboard/tool-matrix")
    assert response.status_code == 200

    body = response.get_json()
    assert len(body["tools"]) == 11
    assert {item["tool"] for item in body["tools"]} == {
        "dashboard",
        "upload",
        "projects",
        "tasks",
        "messenger",
        "email",
        "calendar",
        "time",
        "visualizer",
        "settings",
        "chatbot",
    }
