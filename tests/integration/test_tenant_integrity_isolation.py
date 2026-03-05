from __future__ import annotations

import random
import sqlite3

from flask import g

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


def _seed_user_with_two_tenants(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("TENANT_A", "Tenant A", now)
        auth_db.upsert_tenant("TENANT_B", "Tenant B", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "TENANT_A", "ADMIN", now)
        auth_db.upsert_membership("admin", "TENANT_B", "ADMIN", now)


def _auth_client(app, tenant_id: str):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = tenant_id
    return client


def test_cross_tenant_write_uses_session_tenant_context(tmp_path, monkeypatch):
    from app.tools.memory_store_tool import MemoryStoreTool

    app = _make_app(tmp_path, monkeypatch)
    _seed_user_with_two_tenants(app)

    with app.app_context():
        g.tenant_id = "TENANT_A"
        result = MemoryStoreTool().run(
            content="secret-for-a",
            metadata={"tenant_id": "TENANT_B", "spoof": True},
        )
        assert result["status"] == "stored"

        con = sqlite3.connect(str(app.extensions["auth_db"].path))
        try:
            rows = con.execute("SELECT tenant_id, content FROM agent_memory").fetchall()
        finally:
            con.close()

    assert rows == [("TENANT_A", "secret-for-a")]


def test_cross_tenant_read_does_not_leak_other_tenant_memory(tmp_path, monkeypatch):
    from app.agents.memory_store import MemoryManager

    app = _make_app(tmp_path, monkeypatch)
    _seed_user_with_two_tenants(app)

    with app.app_context():
        manager = MemoryManager(str(app.extensions["auth_db"].path))
        assert manager.store_memory("TENANT_A", "agent", "invoice 123", {"scope": "a"})
        assert manager.store_memory("TENANT_B", "agent", "extremely-secret-B", {"scope": "b"})

        hits = manager.retrieve_context("TENANT_A", "extremely-secret-B", limit=5)

    assert hits
    assert all("TENANT_B" not in str(hit) for hit in hits)
    assert all("extremely-secret-B" not in str(hit.get("content", "")) for hit in hits)


def test_summary_endpoint_is_tenant_bound_for_active_session(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user_with_two_tenants(app)

    client = _auth_client(app, "TENANT_A")
    response = client.get("/api/chatbot/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert body["tenant"] == "TENANT_A"
    assert body["details"]["tenant"] == "TENANT_A"



def test_randomized_tenant_switching_keeps_summary_isolation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user_with_two_tenants(app)

    sequence = [random.choice(["TENANT_A", "TENANT_B"]) for _ in range(12)]
    client = app.test_client()

    for tenant in sequence:
        with client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["role"] = "ADMIN"
            sess["tenant_id"] = tenant

        response = client.get("/api/dashboard/summary")
        assert response.status_code == 200
        body = response.get_json()
        assert body["tenant"] == tenant
        assert body["details"]["tenant"] == tenant


def test_dashboard_tool_matrix_rows_are_tenant_bound(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user_with_two_tenants(app)

    client = _auth_client(app, "TENANT_B")
    response = client.get("/api/dashboard/tool-matrix")
    assert response.status_code == 200

    body = response.get_json()
    assert body["ok"] is True
    assert all(row.get("tenant") == "TENANT_B" for row in body["tools"])
    assert all(row.get("details", {}).get("tenant") == "TENANT_B" for row in body["tools"])
