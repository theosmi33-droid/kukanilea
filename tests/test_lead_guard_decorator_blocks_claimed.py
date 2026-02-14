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


def _set_session(client, *, user: str, tenant: str = "TENANT_A") -> None:
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = tenant


def _new_lead(client) -> str:
    resp = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "Alice",
            "subject": "Dach",
            "message": "Bitte melden",
        },
    )
    assert resp.status_code == 200
    lead_id = (resp.get_json() or {}).get("lead_id")
    assert lead_id
    return lead_id


def test_guard_blocks_non_owner_and_logs_collision(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", ANONYMIZATION_KEY="guard-key")

    owner = app.test_client()
    other = app.test_client()
    _set_session(owner, user="alice")
    _set_session(other, user="bob")

    lead_id = _new_lead(owner)
    assert (
        owner.post(f"/api/leads/{lead_id}/claim", json={"ttl_seconds": 900}).status_code
        == 200
    )

    blocked = other.put(
        f"/api/leads/{lead_id}/assign",
        json={"assigned_to": "bob"},
        headers={"User-Agent": "pytest-guard-agent"},
    )
    assert blocked.status_code == 403
    payload = blocked.get_json() or {}
    assert payload.get("error") == "lead_claimed"
    assert payload.get("lead_id") == lead_id

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        ev = con.execute(
            "SELECT event_type, payload_json FROM events WHERE event_type='lead_claim_collision' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()

    assert ev is not None
    assert str(ev["event_type"]) == "lead_claim_collision"
    assert '"route_key":"leads_assign"' in str(ev["payload_json"])
