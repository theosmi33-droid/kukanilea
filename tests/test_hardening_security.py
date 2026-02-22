from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.auth import AuthDB, hash_password
from app.config import Config


def _make_app(monkeypatch, tmp_path: Path, *, fixed_tenant_enforce: bool = True):
    auth_db = tmp_path / "auth.sqlite3"
    core_db = tmp_path / "core.sqlite3"
    monkeypatch.setattr(Config, "AUTH_DB", auth_db)
    monkeypatch.setattr(Config, "CORE_DB", core_db)
    monkeypatch.setattr(Config, "TENANT_DEFAULT", "KUKANILEA")
    monkeypatch.setattr(Config, "TENANT_NAME", "KUKANILEA")
    core.DB_PATH = core_db
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        READ_ONLY=False,
        TENANT_FIXED_TEST_ENFORCE=fixed_tenant_enforce,
    )
    return app


def _seed_user(app, *, username: str, role: str) -> None:
    auth_db: AuthDB = app.extensions["auth_db"]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user(username, hash_password("pw123456"), now)
    auth_db.upsert_membership(username, "KUKANILEA", role, now)


def _login(
    client, *, username: str = "dev", role: str = "OPERATOR", tenant: str = "KUKANILEA"
) -> None:
    with client.session_transaction() as sess:
        sess["user"] = username
        sess["role"] = role
        sess["tenant_id"] = tenant


def _assert_request_id(response) -> None:
    rid = str(response.headers.get("X-Request-Id") or "").strip()
    assert rid, "Expected X-Request-Id response header"


def test_unauthenticated_requests_are_denied_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()

    for path in ("/api/tasks", "/api/customers", "/api/audit"):
        res = client.get(path)
        assert res.status_code == 401, path
        _assert_request_id(res)
        payload = res.get_json(silent=True) or {}
        assert "password" not in str(payload).lower()
        assert "token" not in str(payload).lower()


def test_low_role_is_denied_on_admin_endpoint(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    _seed_user(app, username="op", role="OPERATOR")
    client = app.test_client()
    _login(client, username="op", role="OPERATOR")

    res = client.get("/api/audit")
    assert res.status_code == 403
    _assert_request_id(res)
    payload = res.get_json(silent=True) or {}
    message = str((payload.get("error") or {}).get("message") or "")
    assert (
        "forbidden" in message.lower()
        or "zugriff" in message.lower()
        or "nicht erlaubt" in message.lower()
        or message == ""
    )


def test_cross_tenant_access_does_not_leak_data(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path, fixed_tenant_enforce=False)
    _seed_user(app, username="alice", role="OPERATOR")
    _seed_user(app, username="bob", role="OPERATOR")
    client = app.test_client()

    core.DB_PATH = app.config["CORE_DB"]
    task_id = int(
        core.task_create(
            tenant="KUKANILEA",
            severity="INFO",
            task_type="GENERAL",
            title="Tenant A Secret Task",
            details="Do not leak",
            created_by="alice",
        )
    )

    _login(client, username="bob", role="OPERATOR", tenant="OTHER_TENANT")
    denied = client.post(f"/api/tasks/{task_id}/move", json={"column": "done"})
    assert denied.status_code in (403, 404)
    _assert_request_id(denied)
    body = denied.get_data(as_text=True)
    assert "Tenant A Secret Task" not in body
    assert "Do not leak" not in body


def test_logout_invalidates_session(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    _seed_user(app, username="dev", role="OPERATOR")
    client = app.test_client()
    _login(client, username="dev", role="OPERATOR")

    before = client.get("/api/tasks")
    assert before.status_code == 200

    out = client.get("/logout", follow_redirects=False)
    assert out.status_code in (302, 303)

    after = client.get("/api/tasks")
    assert after.status_code == 401
    _assert_request_id(after)


def test_csp_header_present_on_html_response(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()

    res = client.get("/login", headers={"Accept": "text/html"})
    assert res.status_code in (200, 302, 303)
    _assert_request_id(res)
    csp = str(res.headers.get("Content-Security-Policy") or "")
    assert "default-src 'self'" in csp
    assert "font-src 'self'" in csp
