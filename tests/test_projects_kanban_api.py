import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


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


def _seed_user(app, username: str, role: str, tenant: str):
    from app.auth import hash_password

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        auth_db.upsert_tenant(tenant, tenant, now)
        auth_db.upsert_user(username, hash_password("pw"), now)
        auth_db.upsert_membership(username, tenant, role, now)


def _login(client, user: str, role: str, tenant: str):
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = role
        sess["tenant_id"] = tenant
        sess["csrf_token"] = "csrf-test"


def test_create_and_move_card_logs_activity_and_memory(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user(app, "alice", "ADMIN", "TENANT_A")
    client = app.test_client()
    _login(client, "alice", "ADMIN", "TENANT_A")

    state_resp = client.get("/api/projects/state")
    assert state_resp.status_code == 200
    state = state_resp.get_json()["state"]
    board_id = state["board"]["id"]
    columns = state["columns"]
    assert len(columns) >= 2

    create_resp = client.post(
        "/api/projects/cards",
        json={
            "board_id": board_id,
            "column_id": columns[0]["id"],
            "title": "Projekt Schmidt klaeren",
            "description": "Status beim Kunden pruefen",
            "due_date": "2026-03-10",
            "assignee": "alice",
        },
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert create_resp.status_code == 200
    card = create_resp.get_json()["card"]

    move_resp = client.post(
        f"/api/projects/cards/{card['id']}/move",
        json={
            "to_column_id": columns[1]["id"],
            "reason": "Kunde Schmidt hat Unterlagen verspaetet geliefert",
        },
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert move_resp.status_code == 200

    state2 = client.get(f"/api/projects/state?board_id={board_id}").get_json()["state"]
    moved = [c for c in state2["cards"] if c["id"] == card["id"]][0]
    assert moved["column_id"] == columns[1]["id"]

    acts = state2["activities"]
    assert any(a["action"] == "CARD_MOVED" for a in acts)

    with app.app_context():
        db_path = str(app.extensions["auth_db"].path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        mem = con.execute(
            """
            SELECT category, content, metadata FROM agent_memory
            WHERE tenant_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            ("TENANT_A",),
        ).fetchone()
        assert mem is not None
        assert mem["category"] == "KANBAN_ACTIVITY"
        assert "CARD_MOVED" in mem["content"]
        assert "Schmidt" in mem["content"]
    finally:
        con.close()


def test_permission_denies_cross_tenant_move(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user(app, "alice", "ADMIN", "TENANT_A")
    _seed_user(app, "bob", "ADMIN", "TENANT_B")

    client = app.test_client()

    _login(client, "alice", "ADMIN", "TENANT_A")
    state_a = client.get("/api/projects/state").get_json()["state"]
    board_a = state_a["board"]["id"]
    col_a = state_a["columns"][0]["id"]
    card_resp = client.post(
        "/api/projects/cards",
        json={"board_id": board_a, "column_id": col_a, "title": "Nur Tenant A"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    card_id = card_resp.get_json()["card"]["id"]

    _login(client, "bob", "ADMIN", "TENANT_B")
    state_b = client.get("/api/projects/state").get_json()["state"]
    col_b = state_b["columns"][1]["id"]

    forbidden = client.post(
        f"/api/projects/cards/{card_id}/move",
        json={"to_column_id": col_b, "reason": "tenant break"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert forbidden.status_code == 403


def test_permission_requires_login(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/api/projects/state")
    assert resp.status_code == 401
