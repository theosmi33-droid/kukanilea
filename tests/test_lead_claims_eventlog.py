from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.event_id_map import entity_id_int
from app.lead_intake.core import (
    lead_claim,
    lead_claims_auto_expire,
    lead_release_claim,
    leads_create,
)

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


def test_claim_events_and_pii_free_payload(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id = leads_create(
        tenant_id="TENANT_A",
        source="manual",
        contact_name="Alice",
        contact_email="alice@example.com",
        contact_phone="+49123456",
        subject="Test",
        message="M",
    )

    lead_claim("TENANT_A", lead_id, actor_user_id="alice", ttl_seconds=900)
    lead_claim("TENANT_A", lead_id, actor_user_id="bob", ttl_seconds=900, force=True)
    lead_release_claim("TENANT_A", lead_id, actor_user_id="bob")

    # recreate active claim then force expiry
    lead_claim("TENANT_A", lead_id, actor_user_id="alice", ttl_seconds=900)
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            "UPDATE lead_claims SET claimed_until='2000-01-01T00:00:00+00:00', released_at=NULL, release_reason=NULL WHERE tenant_id=? AND lead_id=?",
            ("TENANT_A", lead_id),
        )
        con.commit()
    finally:
        con.close()

    lead_claims_auto_expire("TENANT_A", max_actions=10, actor_user_id="ops")

    con2 = sqlite3.connect(str(core.DB_PATH))
    con2.row_factory = sqlite3.Row
    try:
        rows = con2.execute(
            "SELECT event_type, entity_id, payload_json FROM events WHERE event_type IN ('lead_claimed','lead_claim_released','lead_claim_expired','lead_claim_reclaimed') ORDER BY id ASC"
        ).fetchall()
    finally:
        con2.close()

    event_types = [str(r["event_type"]) for r in rows]
    assert "lead_claimed" in event_types
    assert "lead_claim_released" in event_types
    assert "lead_claim_expired" in event_types
    assert "lead_claim_reclaimed" in event_types

    expected_id = entity_id_int(lead_id)
    for row in rows:
        assert int(row["entity_id"]) == expected_id
        payload = json.loads(str(row["payload_json"]))
        text = json.dumps(payload, sort_keys=True)
        for key in _FORBIDDEN:
            assert key not in text
