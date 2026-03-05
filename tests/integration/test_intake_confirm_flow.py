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


def test_intake_execute_requires_explicit_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    normalized = client.post("/api/intake/normalize", json=_payload())
    assert normalized.status_code == 200

    with app.app_context():
        con = sqlite3.connect(app.config["CORE_DB"])
        try:
            before_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        finally:
            con.close()

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
        finally:
            con.close()
    assert count == before_count


def test_intake_execute_confirm_creates_task_and_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    envelope = client.post("/api/intake/normalize", json=_payload()).get_json()["envelope"]

    with app.app_context():
        con = sqlite3.connect(app.config["CORE_DB"])
        try:
            before_task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            before_audit_count = con.execute("SELECT COUNT(*) FROM audit WHERE action='intake_execute_confirmed'").fetchone()[0]
            before_event_count = con.execute("SELECT COUNT(*) FROM events WHERE event_type='intake_execute_confirmed'").fetchone()[0]
        finally:
            con.close()

    resp = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "executed"
    assert body["task"]["task_id"] > 0
    assert body["event_log_id"] > 0

    with app.app_context():
        con = sqlite3.connect(app.config["CORE_DB"])
        try:
            task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            audit_count = con.execute("SELECT COUNT(*) FROM audit WHERE action='intake_execute_confirmed'").fetchone()[0]
            event_count = con.execute("SELECT COUNT(*) FROM events WHERE event_type='intake_execute_confirmed'").fetchone()[0]
        finally:
            con.close()

    assert task_count == before_task_count + 1
    assert audit_count == before_audit_count + 1
    assert event_count == before_event_count + 1
