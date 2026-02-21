from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.config import Config


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path):
    _init_core(tmp_path)
    Config.CORE_DB = core.DB_PATH
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", CORE_DB=core.DB_PATH)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_intake_triage_invoice_label(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/intake/triage",
        json={
            "text": "Bitte Rechnung 2026-44 senden, Zahlung und Mahnung unklar.",
            "metadata": {"channel": "email"},
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert payload.get("ok") is True
    assert payload.get("label") == "invoice"
    assert float(payload.get("confidence") or 0.0) >= 0.3
    assert (payload.get("route") or {}).get("queue") == "billing_inbox"


def test_intake_triage_support_label(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post(
        "/api/intake/triage",
        json={"text": "Störung in der Anlage, bitte dringend Hilfe."},
    )
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert payload.get("label") == "support"
    assert (payload.get("route") or {}).get("priority") == "high"


def test_intake_triage_unknown_label(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/intake/triage", json={"text": "Hallo zusammen"})
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    assert payload.get("label") == "unknown"
    assert (payload.get("route") or {}).get("queue") == "triage_inbox"


def test_intake_triage_validation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/intake/triage", json={"text": "   "})
    assert resp.status_code == 400
    payload = resp.get_json() or {}
    assert (payload.get("error") or {}).get("code") == "validation_error"


def test_intake_triage_requires_auth(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    resp = client.post("/api/intake/triage", json={"text": "anfrage angebot"})
    assert resp.status_code == 401


def test_intake_triage_event_contains_tenant(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/intake/triage", json={"text": "Neukunde Anfrage"})
    assert resp.status_code == 200

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT payload_json FROM events WHERE event_type='intake_triaged' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        payload_json = str(row["payload_json"])
        assert '"tenant_id":"TENANT_A"' in payload_json
        assert '"source":"intake/triage"' in payload_json
    finally:
        con.close()
