from __future__ import annotations

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


def test_tool_summary_and_matrix_are_tenant_scoped(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    summary = client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    summary_body = summary.get_json()
    assert summary_body["details"]["tenant"] == "KUKANILEA"

    matrix = client.get("/api/dashboard/tool-matrix")
    assert matrix.status_code == 200
    matrix_body = matrix.get_json()
    assert matrix_body["tenant"] == "KUKANILEA"
    for row in matrix_body["tools"]:
        assert row["details"]["tenant"] == "KUKANILEA"


def test_contract_normalization_rebinds_tenant_when_collector_leaks(monkeypatch):
    import app.contracts.tool_contracts as contracts

    def _leaky_upload(_tenant: str):
        return {"pending_items": 0}, {"tenant": "OTHER", "source": "broken"}, ""

    monkeypatch.setitem(contracts.SUMMARY_COLLECTORS, "upload", _leaky_upload)
    payload = contracts.build_tool_summary("upload", tenant="KUKANILEA")

    assert payload["details"]["tenant"] == "KUKANILEA"
    assert payload["status"] == "degraded"
    assert payload["degraded_reason"] == "tenant_scope_corrected"


def test_memory_store_degraded_fallback_stays_tenant_local(tmp_path, monkeypatch):
    import sqlite3

    from app.agents.memory_store import MemoryManager

    db_path = tmp_path / "memory.sqlite3"
    con = sqlite3.connect(db_path)
    con.execute(
        """
        CREATE TABLE agent_memory (
            tenant_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            agent_role TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            metadata TEXT NOT NULL,
            importance_score INTEGER NOT NULL,
            category TEXT NOT NULL
        )
        """
    )
    con.commit()
    con.close()

    monkeypatch.setattr("app.agents.memory_store.generate_embedding", lambda _text: [])

    manager = MemoryManager(str(db_path))
    assert manager.store_memory("TENANT_A", "agent", "alpha", {"x": 1}) is True
    assert manager.store_memory("TENANT_B", "agent", "beta", {"x": 2}) is True

    hits_a = manager.retrieve_context("TENANT_A", "frage", limit=10)
    hits_b = manager.retrieve_context("TENANT_B", "frage", limit=10)

    assert len(hits_a) == 1
    assert len(hits_b) == 1
    assert hits_a[0]["content"] == "alpha"
    assert hits_b[0]["content"] == "beta"
    assert hits_a[0]["metadata"]["embedding_status"] == "degraded"
    assert hits_b[0]["metadata"]["embedding_status"] == "degraded"
