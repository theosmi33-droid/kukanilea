from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


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


def test_kalender_summary_endpoint_exists(auth_client):
    response = auth_client.get("/api/kalender/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert "status" in body
    assert "metrics" in body
    assert "details" in body
    assert "events_next_7_days" in body["details"]
    assert "conflicts" in body["details"]
    assert "reminders_due" in body["details"]


def test_kalender_health_endpoint_exists(auth_client):
    response = auth_client.get("/api/kalender/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert "status" in body
    assert "metrics" in body


def test_kalender_events_endpoint_create_update(auth_client):
    _enable_calendar_policy(auth_client)
    create = auth_client.post(
        "/api/kalender/events",
        json={
            "title": "Demo Termin",
            "starts_at": "2031-01-01T09:00:00+00:00",
            "ends_at": "2031-01-01T10:00:00+00:00",
            "reminder_minutes": 30,
        },
    )
    assert create.status_code == 201
    event = create.get_json()["event"]
    assert event["event_id"]

    update = auth_client.patch(
        f"/api/kalender/events/{event['event_id']}",
        json={"title": "Demo Termin (updated)", "reminder_minutes": 45},
    )
    assert update.status_code == 200
    updated = update.get_json()["event"]
    assert updated["event_id"] == event["event_id"]


def test_kalender_events_endpoint_blocks_when_calendar_policy_disabled(auth_client):
    blocked = auth_client.post(
        "/api/kalender/events",
        json={
            "title": "Policy Blocked Termin",
            "starts_at": "2031-01-01T09:00:00+00:00",
            "ends_at": "2031-01-01T10:00:00+00:00",
            "reminder_minutes": 30,
        },
    )
    assert blocked.status_code == 403
    body = blocked.get_json()
    assert body["error"] == "policy_blocked"


def test_kalender_invitation_requires_confirm(auth_client):
    blocked = auth_client.post(
        "/api/kalender/invitations",
        json={
            "title": "Externes Meeting",
            "starts_at": "2031-01-02T09:00:00+00:00",
            "attendees": ["kunde@example.com"],
            "confirm": False,
        },
    )
    assert blocked.status_code == 409
    body = blocked.get_json()
    assert body["error"] == "explicit_confirm_required"

    allowed = auth_client.post(
        "/api/kalender/invitations",
        json={
            "title": "Externes Meeting",
            "starts_at": "2031-01-02T09:00:00+00:00",
            "attendees": ["kunde@example.com"],
            "confirm": True,
        },
    )
    assert allowed.status_code == 202
    assert allowed.get_json()["status"] == "queued"
