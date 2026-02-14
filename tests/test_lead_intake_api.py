from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path, read_only: bool = False):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_lead_api_read_only_blocked(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)
    resp = client.post("/api/leads", json={"source": "manual", "subject": "X"})
    assert resp.status_code == 403
    payload = resp.get_json() or {}
    assert (payload.get("error_code") == "read_only") or (
        payload.get("error", {}).get("code") == "read_only"
    )


def test_lead_api_validation_and_tenant_isolation(tmp_path: Path) -> None:
    client = _client(tmp_path)

    bad = client.post("/api/leads", json={"source": "invalid", "subject": "X"})
    assert bad.status_code == 400

    created = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "Alice",
            "subject": "Dachreparatur",
            "message": "Bitte melden",
        },
    )
    assert created.status_code == 200
    lead_id = (created.get_json() or {}).get("lead_id")
    assert lead_id

    row = client.get(f"/api/leads/{lead_id}")
    assert row.status_code == 200

    with client.session_transaction() as sess:
        sess["tenant_id"] = "TENANT_B"
    denied = client.get(f"/api/leads/{lead_id}")
    assert denied.status_code == 404


def test_actor_user_id_written_to_event_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "Alice",
            "subject": "S1",
            "message": "M1",
        },
    )
    lead_id = (resp.get_json() or {}).get("lead_id")
    assert lead_id

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT payload_json FROM events WHERE event_type='lead_created' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        payload_json = str(row["payload_json"])
        assert '"actor_user_id":"dev"' in payload_json
    finally:
        con.close()
