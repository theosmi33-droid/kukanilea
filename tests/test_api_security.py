from __future__ import annotations

from datetime import datetime

from app import create_app, web
from app.auth import hash_password
from app.db import AuthDB


def _setup_app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("DB_FILENAME", str(tmp_path / "core.db"))
    app = create_app()
    auth_db: AuthDB = app.extensions["auth_db"]
    now = datetime.utcnow().isoformat()
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user("admin", hash_password("admin"), now)
    auth_db.upsert_user("alice", hash_password("alice"), now)
    auth_db.upsert_user("bob", hash_password("bob"), now)
    auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    auth_db.upsert_membership("alice", "KUKANILEA", "OPERATOR", now)
    auth_db.upsert_membership("bob", "KUKANILEA", "OPERATOR", now)
    web.core.DB_PATH = tmp_path / "core.db"
    web.core.db_init()
    return app


def test_csrf_missing(monkeypatch, tmp_path):
    app = _setup_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    res = client.post("/api/chat", json={"q": "rechnung"})
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"]["code"] == "csrf_missing"


def test_csrf_invalid(monkeypatch, tmp_path):
    app = _setup_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    res = client.post("/api/chat", json={"q": "rechnung"}, headers={"X-CSRF-Token": "bad"})
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"]["code"] == "csrf_invalid"


def test_rate_limit_exceeded(monkeypatch, tmp_path):
    app = _setup_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    web.chat_limiter.limit = 1
    web.chat_limiter.hits.clear()

    first = client.post("/api/chat", json={"q": "rechnung"}, headers={"X-CSRF-Token": "token"})
    assert first.status_code == 200
    second = client.post("/api/chat", json={"q": "rechnung"}, headers={"X-CSRF-Token": "token"})
    assert second.status_code == 429
    data = second.get_json()
    assert data["error"]["code"] == "rate_limited"


def test_forbidden_customer_lookup(monkeypatch, tmp_path):
    app = _setup_app(tmp_path, monkeypatch)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "bob"
        sess["role"] = "READONLY"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    res = client.post("/api/customer", json={"kdnr": "12345"}, headers={"X-CSRF-Token": "token"})
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"]["code"] == "forbidden"


def test_time_entry_ownership(monkeypatch, tmp_path):
    app = _setup_app(tmp_path, monkeypatch)
    project = web.core.time_project_create(tenant_id="KUKANILEA", name="Test", created_by="admin")
    entry = web.core.time_entry_start(tenant_id="KUKANILEA", user="alice", project_id=project["id"])
    web.core.time_entry_stop(tenant_id="KUKANILEA", user="alice", entry_id=entry["id"])

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "bob"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    res = client.post(
        "/api/time/entry/edit",
        json={"entry_id": entry["id"], "note": "oops"},
        headers={"X-CSRF-Token": "token"},
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["error"]["code"] == "forbidden"

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    res = client.post(
        "/api/time/entry/edit",
        json={"entry_id": entry["id"], "note": "admin ok"},
        headers={"X-CSRF-Token": "token"},
    )
    assert res.status_code == 200


def test_time_entry_stop_on_closed(monkeypatch, tmp_path):
    app = _setup_app(tmp_path, monkeypatch)
    project = web.core.time_project_create(tenant_id="KUKANILEA", name="Test", created_by="admin")
    entry = web.core.time_entry_start(tenant_id="KUKANILEA", user="alice", project_id=project["id"])
    web.core.time_entry_stop(tenant_id="KUKANILEA", user="alice", entry_id=entry["id"])

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "token"

    res = client.post(
        "/api/time/stop",
        json={"entry_id": entry["id"]},
        headers={"X-CSRF-Token": "token"},
    )
    assert res.status_code == 409
    data = res.get_json()
    assert data["error"]["code"] == "timer_already_stopped"
