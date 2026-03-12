from __future__ import annotations

import sqlite3

from app import create_app


def _seed_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def _payload() -> dict:
    return {
        "source": "mail",
        "thread_id": "thread-123",
        "sender": "kunde@example.com",
        "subject": "Bitte Angebot bis Freitag",
        "snippets": ["Bitte als Task aufnehmen."],
        "attachments": [{"filename": "brief.pdf", "id": "att-1", "content_type": "application/pdf"}],
        "project_hint": "Kundenprojekt Alpha",
        "calendar_hint": "Rückruf Kundin",
        "due_date": "2030-05-01T10:00:00+00:00",
    }


def test_intake_normalize_includes_deterministic_task_proposal_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()

    _seed_session(client)

    payload = _payload()
    first = client.post("/api/intake/normalize", json=payload)
    second = client.post("/api/intake/normalize", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200

    first_action = first.get_json()["envelope"]["suggested_actions"][0]
    second_action = second.get_json()["envelope"]["suggested_actions"][0]

    assert first_action["type"] == "create_task"
    assert first_action["proposal_ref"].startswith("intake-proposal-")
    assert first_action["proposal_ref"] == second_action["proposal_ref"]
    assert first_action["trace"] == {
        "source": payload["source"],
        "thread_id": payload["thread_id"],
        "sender": payload["sender"],
    }


def test_intake_execute_requires_explicit_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    normalized = client.post("/api/intake/normalize", json=_payload())
    assert normalized.status_code == 200

    resp = client.post(
        "/api/intake/execute",
        json={"envelope": normalized.get_json()["envelope"], "requires_confirm": True, "confirm": "no"},
    )
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["status"] == "blocked"

    with app.app_context():
        con = sqlite3.connect(app.config["CORE_DB"])
        try:
            count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            mia_confirm_denied = con.execute("SELECT COUNT(*) FROM events WHERE event_type='mia.confirm.denied'").fetchone()[0]
        finally:
            con.close()
    assert count == 0
    assert mia_confirm_denied == 1


def test_intake_execute_confirm_creates_task_and_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    envelope = client.post("/api/intake/normalize", json=_payload()).get_json()["envelope"]
    resp = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "executed"
    assert body["task"]["task_id"] > 0
    assert body["event_log_id"] > 0
    assert body["mia_event_ids"]["proposal_created"] > 0
    assert body["mia_event_ids"]["confirm_requested"] > 0
    assert body["mia_event_ids"]["confirm_granted"] > 0
    assert body["mia_event_ids"]["execution_started"] > 0
    assert body["mia_event_ids"]["execution_finished"] > 0
    assert body["mia_event_ids"]["audit_trail_linked"] > 0

    with app.app_context():
        con = sqlite3.connect(app.config["CORE_DB"])
        try:
            task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            audit_count = con.execute("SELECT COUNT(*) FROM audit WHERE action='intake_execute_confirmed'").fetchone()[0]
            event_count = con.execute("SELECT COUNT(*) FROM events WHERE event_type='intake_execute_confirmed'").fetchone()[0]
            mia_count = con.execute("SELECT COUNT(*) FROM events WHERE event_type LIKE 'mia.%'").fetchone()[0]
        finally:
            con.close()

    assert task_count == 1
    assert audit_count == 1
    assert event_count == 1
    assert mia_count >= 6


def test_intake_execute_forbids_readonly_role(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "readonly-user"
        sess["role"] = "READONLY"
        sess["tenant_id"] = "KUKANILEA"

    envelope = client.post("/api/intake/normalize", json=_payload()).get_json()["envelope"]
    resp = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
    )

    assert resp.status_code == 403

    with app.app_context():
        con = sqlite3.connect(app.config["CORE_DB"])
        try:
            task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        finally:
            con.close()

    assert task_count == 0
