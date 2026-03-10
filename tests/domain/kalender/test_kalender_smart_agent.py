from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from app.modules.kalender import contracts


def _enable_calendar_policy(auth_client) -> None:
    db_path = str(auth_client.application.config["CORE_DB"])
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_source_policies(
              tenant_id TEXT PRIMARY KEY,
              allow_manual INTEGER NOT NULL DEFAULT 1,
              allow_tasks INTEGER NOT NULL DEFAULT 1,
              allow_projects INTEGER NOT NULL DEFAULT 1,
              allow_documents INTEGER NOT NULL DEFAULT 0,
              allow_leads INTEGER NOT NULL DEFAULT 0,
              allow_email INTEGER NOT NULL DEFAULT 0,
              allow_calendar INTEGER NOT NULL DEFAULT 0,
              allow_ocr INTEGER NOT NULL DEFAULT 0,
              allow_customer_pii INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            INSERT OR REPLACE INTO knowledge_source_policies(
              tenant_id, allow_manual, allow_tasks, allow_projects, allow_documents,
              allow_leads, allow_email, allow_calendar, allow_ocr, allow_customer_pii, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "KUKANILEA",
                1,
                1,
                1,
                0,
                0,
                0,
                1,
                0,
                1,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        con.commit()


def test_document_processed_event_creates_deadline_event(auth_client):
    _enable_calendar_policy(auth_client)
    payload = contracts.handle_document_processed_event(
        "KUKANILEA",
        {
            "actor": "ocr-worker",
            "deadlines": [
                {
                    "title": "Frist aus Rechnung #77",
                    "due_date": "2031-02-01T08:00:00+00:00",
                    "reminder_minutes": 120,
                }
            ],
        },
    )
    assert payload["count"] == 1
    created = payload["created"][0]
    assert created["title"] == "Frist aus Rechnung #77"
    assert created["reminder_minutes"] == 120


def test_kalender_summary_reports_conflicts_and_reminders(auth_client):
    _enable_calendar_policy(auth_client)
    base = datetime.now(UTC) + timedelta(hours=2)
    start_a = base.replace(minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    end_a = (base.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).isoformat(timespec="seconds")
    start_b = (base.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=30)).isoformat(timespec="seconds")
    end_b = (base.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)).isoformat(timespec="seconds")

    contracts.create_event(
        tenant="KUKANILEA",
        title="Konflikt A",
        starts_at=start_a,
        ends_at=end_a,
        reminder_minutes=15,
        created_by="tester",
    )
    contracts.create_event(
        tenant="KUKANILEA",
        title="Konflikt B",
        starts_at=start_b,
        ends_at=end_b,
        reminder_minutes=15,
        created_by="tester",
    )

    summary = contracts.build_summary("KUKANILEA")
    assert isinstance(summary["events_next_7_days"], list)
    assert isinstance(summary["conflicts"], list)
    assert isinstance(summary["reminders_due"], list)
    assert summary["metrics"]["conflicts"] >= 1


def test_demo_scenario_confirm_gate_and_summary(auth_client):
    _enable_calendar_policy(auth_client)
    meeting = auth_client.post(
        "/api/kalender/events",
        json={
            "title": "Demo Kickoff",
            "starts_at": "2031-04-02T09:00:00+00:00",
            "ends_at": "2031-04-02T10:00:00+00:00",
            "reminder_minutes": 30,
        },
    )
    assert meeting.status_code == 201

    blocked = auth_client.post(
        "/api/kalender/invitations",
        json={
            "title": "Demo Kickoff",
            "starts_at": "2031-04-02T09:00:00+00:00",
            "attendees": ["partner@example.com"],
            "confirm": False,
        },
    )
    assert blocked.status_code == 409

    allowed = auth_client.post(
        "/api/kalender/invitations",
        json={
            "title": "Demo Kickoff",
            "starts_at": "2031-04-02T09:00:00+00:00",
            "attendees": ["partner@example.com"],
            "confirm": True,
        },
    )
    assert allowed.status_code == 202

    summary = auth_client.get("/api/kalender/summary")
    assert summary.status_code == 200
    body = summary.get_json()
    assert body["window_days"] == 7
