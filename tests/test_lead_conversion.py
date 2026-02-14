from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app

FORBIDDEN_KEYS = {
    "contact_email",
    "contact_phone",
    "contact_name",
    "subject",
    "message",
    "notes",
    "body",
    "email",
    "phone",
}


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
            "contact_email": "alice@example.com",
            "contact_phone": "+491701234567",
            "subject": "Dachsanierung am Objekt",
            "message": "Bitte Angebot erstellen",
        },
    )
    assert resp.status_code == 200
    lead_id = (resp.get_json() or {}).get("lead_id")
    assert lead_id
    return str(lead_id)


def _all_payload_keys(payload: object) -> set[str]:
    out: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            out.add(str(key))
            out |= _all_payload_keys(value)
    elif isinstance(payload, list):
        for value in payload:
            out |= _all_payload_keys(value)
    return out


def test_lead_conversion_creates_deal_quote_and_links(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    client = app.test_client()
    _set_session(client, user="alice", tenant="TENANT_A")

    lead_id = _new_lead(client)
    claim = client.post(f"/api/leads/{lead_id}/claim", json={"ttl_seconds": 900})
    assert claim.status_code == 200

    convert = client.post(
        f"/api/leads/{lead_id}/convert",
        json={
            "deal_title": "",
            "customer_name": "",
            "use_subject_title": False,
            "use_contact_name": False,
        },
    )
    assert convert.status_code == 200
    payload = convert.get_json() or {}
    assert payload.get("ok") is True
    deal_id = str(payload.get("deal_id") or "")
    quote_id = str(payload.get("quote_id") or "")
    customer_id = str(payload.get("customer_id") or "")
    assert deal_id and quote_id and customer_id

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        lead = con.execute(
            "SELECT tenant_id, status, customer_id FROM leads WHERE id=?",
            (lead_id,),
        ).fetchone()
        assert lead is not None
        assert str(lead["tenant_id"]) == "TENANT_A"
        assert str(lead["status"]) == "qualified"
        assert str(lead["customer_id"]) == customer_id

        deal = con.execute(
            "SELECT tenant_id, customer_id FROM deals WHERE tenant_id=? AND id=?",
            ("TENANT_A", deal_id),
        ).fetchone()
        assert deal is not None
        assert str(deal["customer_id"]) == customer_id

        quote = con.execute(
            "SELECT tenant_id, customer_id, deal_id, status FROM quotes WHERE tenant_id=? AND id=?",
            ("TENANT_A", quote_id),
        ).fetchone()
        assert quote is not None
        assert str(quote["customer_id"]) == customer_id
        assert str(quote["deal_id"]) == deal_id
        assert str(quote["status"]) == "draft"

        links = con.execute(
            """
            SELECT a_type, a_id, b_type, b_id, link_type
            FROM entity_links
            WHERE tenant_id=? AND link_type='converted_from'
              AND ((a_type='lead' AND a_id=?) OR (b_type='lead' AND b_id=?))
            """,
            ("TENANT_A", lead_id, lead_id),
        ).fetchall()
        assert len(links) >= 2
        assert any(
            {
                str(r["a_type"]),
                str(r["b_type"]),
            }
            == {"lead", "deal"}
            for r in links
        )
        assert any(
            {
                str(r["a_type"]),
                str(r["b_type"]),
            }
            == {"lead", "quote"}
            for r in links
        )

        events = con.execute(
            """
            SELECT event_type, payload_json
            FROM events
            WHERE event_type IN ('lead_converted','deal_created_from_lead')
            ORDER BY id ASC
            """
        ).fetchall()
        assert events
        for event in events:
            data = json.loads(str(event["payload_json"] or "{}"))
            keys = _all_payload_keys(data)
            assert not (keys & FORBIDDEN_KEYS)
    finally:
        con.close()


def test_lead_conversion_blocked_when_claimed_by_other_user(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    c1 = app.test_client()
    c2 = app.test_client()
    _set_session(c1, user="alice", tenant="TENANT_A")
    _set_session(c2, user="bob", tenant="TENANT_A")

    lead_id = _new_lead(c1)
    assert (
        c1.post(f"/api/leads/{lead_id}/claim", json={"ttl_seconds": 900}).status_code
        == 200
    )

    blocked = c2.post(f"/api/leads/{lead_id}/convert", json={})
    assert blocked.status_code == 403
    payload = blocked.get_json() or {}
    assert payload.get("error") == "lead_claimed"


def test_lead_conversion_is_tenant_isolated(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    c1 = app.test_client()
    c2 = app.test_client()
    _set_session(c1, user="alice", tenant="TENANT_A")
    _set_session(c2, user="bob", tenant="TENANT_B")

    lead_id = _new_lead(c1)
    not_found = c2.post(f"/api/leads/{lead_id}/convert", json={})
    assert not_found.status_code == 404
    body = not_found.get_json() or {}
    assert body.get("error") == "not_found"


def test_lead_conversion_read_only_blocked(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    client = app.test_client()
    _set_session(client, user="alice", tenant="TENANT_A")
    lead_id = _new_lead(client)

    app.config["READ_ONLY"] = True
    resp = client.post(f"/api/leads/{lead_id}/convert", json={})
    assert resp.status_code == 403
    body = resp.get_json() or {}
    assert (body.get("error_code") == "read_only") or (
        (body.get("error") or {}).get("code") == "read_only"
    )
