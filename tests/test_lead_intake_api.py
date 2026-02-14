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


def _create_lead(client) -> str:
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
    return lead_id


def test_lead_api_read_only_blocks_all_new_posts(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)

    lead_id = "abc123"
    routes = [
        ("POST", "/api/leads", {"source": "manual", "subject": "X"}),
        ("POST", f"/api/leads/{lead_id}/screen/accept", {}),
        ("POST", f"/api/leads/{lead_id}/screen/ignore", {}),
        ("PUT", f"/api/leads/{lead_id}/priority", {"priority": "high", "pinned": 1}),
        ("PUT", f"/api/leads/{lead_id}/assign", {"assigned_to": "dev"}),
        ("POST", "/api/leads/blocklist", {"kind": "email", "value": "a@example.com"}),
    ]

    for method, url, body in routes:
        resp = client.open(url, method=method, json=body)
        assert resp.status_code == 403
        payload = resp.get_json() or {}
        assert (payload.get("error_code") == "read_only") or (
            payload.get("error", {}).get("code") == "read_only"
        )


def test_lead_api_validation_and_tenant_isolation(tmp_path: Path) -> None:
    client = _client(tmp_path)

    bad = client.post("/api/leads", json={"source": "invalid", "subject": "X"})
    assert bad.status_code == 400

    lead_id = _create_lead(client)

    row = client.get(f"/api/leads/{lead_id}")
    assert row.status_code == 200

    with client.session_transaction() as sess:
        sess["tenant_id"] = "TENANT_B"
    denied = client.get(f"/api/leads/{lead_id}")
    assert denied.status_code == 404


def test_actor_user_id_written_to_event_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)
    lead_id = _create_lead(client)
    assert lead_id

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT payload_json FROM events WHERE event_type IN ('lead_created','lead_blocked') ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        payload_json = str(row["payload_json"])
        assert '"actor_user_id":"dev"' in payload_json
    finally:
        con.close()


def test_xss_payload_is_escaped_in_ui(tmp_path: Path) -> None:
    client = _client(tmp_path)
    bad_subject = "<script>alert(1)</script>"
    resp = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "X",
            "subject": bad_subject,
            "message": "m",
        },
    )
    lead_id = (resp.get_json() or {}).get("lead_id")
    assert lead_id

    inbox = client.get("/leads/inbox?tab=all")
    text = inbox.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text

    detail = client.get(f"/leads/{lead_id}")
    dtext = detail.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in dtext


def test_ics_crlf_injection_is_sanitized(tmp_path: Path) -> None:
    client = _client(tmp_path)
    subject = "Bad\\r\\nBEGIN:VEVENT"
    resp = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "X",
            "subject": subject,
            "message": "m",
        },
    )
    lead_id = (resp.get_json() or {}).get("lead_id")
    assert lead_id

    appt = client.post(
        "/api/appointment-requests",
        json={
            "lead_id": lead_id,
            "requested_date": "2026-03-01T10:00:00+00:00",
            "notes": "n",
        },
    )
    appt_id = (appt.get_json() or {}).get("appointment_request_id")
    assert appt_id

    ics = client.get(f"/api/appointment-requests/{appt_id}/ics")
    assert ics.status_code == 200
    body = ics.get_data(as_text=True)
    # only one VEVENT block, no injected second block
    assert body.count("BEGIN:VEVENT") == 1
