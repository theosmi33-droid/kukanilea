from __future__ import annotations

from app import create_app


def _seed_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def test_intake_normalize_adds_appointment_proposal(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    response = client.post(
        "/api/intake/normalize",
        json={
            "source": "mail",
            "thread_id": "proposal-1",
            "subject": "Termin für Projekt",
            "project_hint": "Projekt A",
            "calendar_hint": "Besprechung",
            "due_date": "2030-08-01T09:00:00+00:00",
        },
    )

    assert response.status_code == 200
    actions = response.get_json()["envelope"]["suggested_actions"]
    appointment = [item for item in actions if item.get("type") == "create_appointment"]
    assert appointment
    assert appointment[0]["mode"] == "proposal"
    assert appointment[0]["requires_confirm"] is True


def test_intake_execute_creates_appointment_only_after_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    envelope = client.post(
        "/api/intake/normalize",
        json={
            "source": "mail",
            "thread_id": "proposal-2",
            "subject": "Termin für Projekt",
            "project_hint": "Projekt A",
            "due_date": "2030-08-01T09:00:00+00:00",
        },
    ).get_json()["envelope"]

    blocked = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "no"},
    )
    assert blocked.status_code == 409

    confirmed = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "yes"},
    )
    assert confirmed.status_code == 200
    assert confirmed.get_json()["calendar"] is not None

    calendar_payload = confirmed.get_json()["calendar"]
    assert calendar_payload.get("event_id") or calendar_payload.get("status") == "proposal_only"


def test_intake_normalize_adds_proposal_for_task_calendar_context_without_due_date(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    response = client.post(
        "/api/intake/normalize",
        json={
            "source": "mail",
            "thread_id": "proposal-3",
            "subject": "Task mit offenem Termin",
            "project_hint": "Projekt B",
            "calendar_hint": "Kickoff abstimmen",
        },
    )

    assert response.status_code == 200
    actions = response.get_json()["envelope"]["suggested_actions"]
    appointment = [item for item in actions if item.get("type") == "create_appointment"]
    assert appointment
    assert appointment[0]["mode"] == "proposal"
    assert appointment[0]["requires_confirm"] is True
    assert appointment[0]["starts_at"] is None
