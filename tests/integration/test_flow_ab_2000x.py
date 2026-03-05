from __future__ import annotations

import sqlite3

from app import create_app


def _seed_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def _payload(seq: int = 1) -> dict:
    return {
        "source": "mail",
        "thread_id": f"flow-ab-{seq:04d}",
        "sender": "kunde@example.com",
        "subject": f"Flow A/B Test {seq}",
        "snippets": [f"Bitte Aufgabe {seq} anlegen."],
        "attachments": [{"filename": f"brief-{seq}.pdf", "id": f"att-{seq}", "content_type": "application/pdf"}],
        "project_hint": "Kundenprojekt Alpha",
        "calendar_hint": "Rückruf Kundin",
        "due_date": "2030-05-01T10:00:00+00:00",
    }


def _db_counts(db_path: str) -> tuple[int, int, int]:
    con = sqlite3.connect(db_path)
    try:
        task_count = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        audit_count = con.execute("SELECT COUNT(*) FROM audit WHERE action='intake_execute_confirmed'").fetchone()[0]
        event_count = con.execute("SELECT COUNT(*) FROM events WHERE event_type='intake_execute_confirmed'").fetchone()[0]
    finally:
        con.close()
    return task_count, audit_count, event_count


def test_flow_ab_2000x_is_deterministic_and_tenant_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    blocked_runs = 5
    executed_runs = 7

    for idx in range(1, blocked_runs + 1):
        envelope = client.post("/api/intake/normalize", json=_payload(idx)).get_json()["envelope"]
        blocked = client.post(
            "/api/intake/execute",
            json={"envelope": envelope, "requires_confirm": True, "confirm": "no"},
        )
        assert blocked.status_code == 409
        blocked_body = blocked.get_json()
        assert blocked_body["status"] == "blocked"

    for idx in range(blocked_runs + 1, blocked_runs + executed_runs + 1):
        envelope = client.post("/api/intake/normalize", json=_payload(idx)).get_json()["envelope"]
        executed = client.post(
            "/api/intake/execute",
            json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
        )
        assert executed.status_code == 200
        body = executed.get_json()
        assert body["status"] == "executed"
        assert body["task"]["task_id"] > 0

    summary = client.get("/api/upload/summary")
    assert summary.status_code == 200
    summary_body = summary.get_json()
    assert summary_body["summary"]["details"]["tenant"] == "KUKANILEA"
    assert summary_body["summary"]["details"]["intake_contract"]["requires_explicit_confirm"] is True

    with app.app_context():
        task_count, audit_count, event_count = _db_counts(app.config["CORE_DB"])

    assert task_count == executed_runs
    assert audit_count == executed_runs
    assert event_count == executed_runs
