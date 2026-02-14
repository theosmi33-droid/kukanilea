from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.event_id_map import entity_id_int

_FORBIDDEN = [
    "contact_email",
    "contact_phone",
    "subject",
    "message",
    "notes",
]


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


def test_collision_event_emitted_on_claim_guard_block(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        ANONYMIZATION_KEY="collision-key",
        READ_ONLY=False,
    )

    c1 = app.test_client()
    c2 = app.test_client()
    _set_session(c1, user="alice")
    _set_session(c2, user="bob")

    lead_id = _new_lead(c1)

    claimed = c1.post(f"/api/leads/{lead_id}/claim", json={"ttl_seconds": 900})
    assert claimed.status_code == 200

    ua = "pytest-collision-agent"
    blocked = c2.put(
        f"/api/leads/{lead_id}/priority",
        json={"priority": "high", "pinned": 1},
        headers={"User-Agent": ua},
    )
    assert blocked.status_code == 403
    assert (blocked.get_json() or {}).get("error") == "lead_claimed"

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT event_type, entity_id, payload_json FROM events WHERE event_type='lead_claim_collision' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert str(row["event_type"]) == "lead_claim_collision"
    assert int(row["entity_id"]) == entity_id_int(lead_id)

    payload = json.loads(str(row["payload_json"] or "{}"))
    data = payload.get("data") or {}

    assert data.get("lead_id") == lead_id
    assert data.get("route_key") == "leads_priority"
    assert data.get("claimed_by_user_id") == "alice"
    assert (
        data.get("ua_hash")
        == hmac.new(b"collision-key", ua.encode("utf-8"), hashlib.sha256).hexdigest()
    )

    encoded = json.dumps(payload, sort_keys=True)
    assert ua not in encoded
    for key in _FORBIDDEN:
        assert key not in encoded
