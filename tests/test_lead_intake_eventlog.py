from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_verify_chain
from app.lead_intake.core import (
    appointment_requests_create,
    appointment_requests_update_status,
    call_logs_create,
    leads_add_note,
    leads_block_sender,
    leads_create,
    leads_set_priority,
    leads_update_status,
)

PII_KEYS = {
    "contact_email",
    "contact_phone",
    "contact_name",
    "subject",
    "message",
    "notes",
    "caller_phone",
    "description",
}


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _event_count() -> int:
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        row = con.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def _all_payload_keys(payload: object) -> set[str]:
    out: set[str] = set()
    if isinstance(payload, dict):
        for k, v in payload.items():
            out.add(str(k))
            out |= _all_payload_keys(v)
    elif isinstance(payload, list):
        for v in payload:
            out |= _all_payload_keys(v)
    return out


def test_entity_id_int_is_deterministic() -> None:
    assert entity_id_int("abc") == entity_id_int("abc")
    assert entity_id_int("abc") != entity_id_int("abd")


def test_blocked_lead_creates_lead_blocked_event(tmp_path: Path) -> None:
    _init_core(tmp_path)
    leads_block_sender("TENANT_A", "email", "spam@example.com", "dev")
    lead_id = leads_create(
        tenant_id="TENANT_A",
        source="email",
        contact_name="Spam",
        contact_email="spam@example.com",
        contact_phone="",
        subject="Offer",
        message="spam",
    )

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        lead = con.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()
        assert lead and lead["status"] == "ignored"
        ev = con.execute(
            "SELECT event_type, payload_json FROM events WHERE event_type='lead_blocked' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert ev is not None
    finally:
        con.close()


def test_each_mutation_writes_event_and_payload_has_no_pii(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id = leads_create(
        tenant_id="TENANT_A",
        source="manual",
        contact_name="Max",
        contact_email="max@example.com",
        contact_phone="123",
        subject="Neu",
        message="Bitte zurückrufen",
        notes="private",
    )

    before = _event_count()
    leads_update_status("TENANT_A", lead_id, "contacted")
    assert _event_count() == before + 1

    before = _event_count()
    leads_set_priority("TENANT_A", lead_id, "high", 1, "dev")
    assert _event_count() == before + 1

    before = _event_count()
    leads_add_note("TENANT_A", lead_id, "interne notiz")
    assert _event_count() == before + 1

    before = _event_count()
    call_logs_create("TENANT_A", lead_id, "Max", "123", "inbound", 60, "private")
    assert _event_count() == before + 1

    before = _event_count()
    req_id = appointment_requests_create("TENANT_A", lead_id, None, "notiz")
    assert _event_count() == before + 1

    before = _event_count()
    appointment_requests_update_status("TENANT_A", req_id, "accepted")
    assert _event_count() == before + 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT payload_json FROM events ORDER BY id ASC").fetchall()
    finally:
        con.close()

    for row in rows:
        payload = json.loads(str(row["payload_json"] or "{}"))
        keys = _all_payload_keys(payload)
        assert not (keys & PII_KEYS)

    con2 = sqlite3.connect(str(core.DB_PATH))
    con2.row_factory = sqlite3.Row
    try:
        ok, bad_id, reason = event_verify_chain(con=con2)
    finally:
        con2.close()
    assert ok, (bad_id, reason)
