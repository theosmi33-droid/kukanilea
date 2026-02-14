from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.lead_intake.core import (
    appointment_requests_create,
    call_logs_create,
    lead_claim,
    lead_release_claim,
    leads_add_note,
    leads_create,
    leads_set_priority,
)

FORBIDDEN_TOKENS = [
    '"contact_email"',
    '"contact_phone"',
    '"subject"',
    '"message"',
    '"notes"',
    '"body"',
    '"email"',
    '"phone"',
]


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_eventlog_payloads_stay_pii_safe_for_lead_flow(tmp_path: Path) -> None:
    _init_core(tmp_path)

    lead_id = leads_create(
        tenant_id="TENANT_A",
        source="manual",
        contact_name="Alice",
        contact_email="alice@example.com",
        contact_phone="+491701234567",
        subject="Secret Angebot",
        message="Bitte an alice@example.com senden",
        notes="private notes",
    )
    leads_add_note("TENANT_A", lead_id, "Interne Notiz")
    leads_set_priority("TENANT_A", lead_id, "high", 1, actor_user_id="alice")
    call_logs_create(
        "TENANT_A",
        lead_id,
        "Caller",
        "+491234",
        "inbound",
        42,
        "Private call note",
        actor_user_id="alice",
    )
    appointment_requests_create(
        "TENANT_A",
        lead_id,
        "2026-02-14T10:00:00+00:00",
        "Private appointment note",
        actor_user_id="alice",
    )
    lead_claim("TENANT_A", lead_id, actor_user_id="alice", ttl_seconds=300)
    lead_release_claim("TENANT_A", lead_id, actor_user_id="alice")

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT payload_json FROM events ORDER BY id ASC").fetchall()
    finally:
        con.close()

    assert rows, "Expected eventlog entries"
    for row in rows:
        payload = str(row["payload_json"] or "").lower()
        for token in FORBIDDEN_TOKENS:
            assert token not in payload, f"Forbidden token {token} in payload {payload}"
