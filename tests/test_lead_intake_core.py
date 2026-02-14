from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.lead_intake.core import (
    appointment_requests_create,
    appointment_requests_get,
    appointment_requests_update_status,
    call_logs_create,
    leads_add_note,
    leads_create,
    leads_get,
    leads_list,
    leads_update_status,
)


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


def test_lead_intake_core_crud_and_tenant_scoping(tmp_path: Path) -> None:
    _init_core(tmp_path)

    lead_id = leads_create(
        tenant_id="TENANT_A",
        source="manual",
        contact_name="Max",
        contact_email="max@example.com",
        contact_phone="123",
        subject="Neue Anfrage",
        message="Bitte Angebot",
    )
    assert leads_get("TENANT_A", lead_id)
    assert leads_get("TENANT_B", lead_id) is None

    rows = leads_list("TENANT_A", q="Neue", limit=20, offset=0)
    assert any(r["id"] == lead_id for r in rows)

    before = _event_count()
    leads_update_status("TENANT_A", lead_id, "qualified")
    assert _event_count() == before + 1

    before = _event_count()
    leads_add_note("TENANT_A", lead_id, "Rückruf morgen")
    assert _event_count() == before + 1

    before = _event_count()
    call_id = call_logs_create(
        "TENANT_A",
        lead_id,
        "Max",
        "123",
        "inbound",
        120,
        "Telefonat",
    )
    assert isinstance(call_id, str) and call_id
    assert _event_count() == before + 1

    before = _event_count()
    req_id = appointment_requests_create(
        "TENANT_A",
        lead_id,
        "2026-03-01T10:00:00+00:00",
        "Vor-Ort",
    )
    assert _event_count() == before + 1
    req = appointment_requests_get("TENANT_A", req_id)
    assert req and req["status"] == "pending"

    before = _event_count()
    appointment_requests_update_status("TENANT_A", req_id, "accepted")
    assert _event_count() == before + 1
    req2 = appointment_requests_get("TENANT_A", req_id)
    assert req2 and req2["status"] == "accepted"
