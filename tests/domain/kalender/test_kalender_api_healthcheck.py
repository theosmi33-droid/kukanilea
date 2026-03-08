from __future__ import annotations


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


def test_kalender_events_endpoint_blocked_in_read_only_mode(auth_client):
    auth_client.application.config["READ_ONLY"] = True
    blocked = auth_client.post(
        "/api/kalender/events",
        json={
            "title": "Blocked Termin",
            "starts_at": "2031-01-03T09:00:00+00:00",
        },
    )
    assert blocked.status_code == 403
    body = blocked.get_json()
    assert body["error"]["code"] == "read_only"
