from __future__ import annotations

import re
from datetime import datetime, timezone

from app import create_app
from app.auth import hash_password
from app.db import AuthDB


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _csrf_from_login(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else ""


def test_upsert_user_keeps_memberships(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    auth_db = AuthDB(db_path)
    auth_db.init()
    now = _now_iso()

    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user("dev", hash_password("dev"), now)
    auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    auth_db.upsert_user("dev", hash_password("dev"), _now_iso())

    memberships = auth_db.get_memberships("dev")
    assert len(memberships) == 1
    assert memberships[0].tenant_id == "KUKANILEA"


def test_dev_login_bootstraps_system_tenant_without_fk_error(tmp_path, monkeypatch):
    auth_db_path = tmp_path / "auth.sqlite3"
    core_db_path = tmp_path / "core.sqlite3"
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db_path))
    monkeypatch.setenv("DB_FILENAME", str(core_db_path))
    monkeypatch.setenv("BASE_DIRNAME", "Kukanilea_Test")
    monkeypatch.setenv("HOME", str(tmp_path))

    app = create_app()
    with app.app_context():
        auth_db: AuthDB = app.extensions["auth_db"]
        auth_db.upsert_user("dev", hash_password("dev"), _now_iso())
        # no membership on purpose

    client = app.test_client()
    login_page = client.get("/login")
    token = _csrf_from_login(login_page.get_data(as_text=True))

    resp = client.post(
        "/login",
        data={"username": "dev", "password": "dev", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        system_tenant = auth_db.get_tenant("SYSTEM")
        dev_memberships = auth_db.get_memberships("dev")
        assert system_tenant is not None
        assert any(m.tenant_id == "SYSTEM" for m in dev_memberships)
