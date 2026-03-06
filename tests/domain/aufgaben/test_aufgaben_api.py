from __future__ import annotations

from app.services.shared_services import shared_services


def test_aufgaben_crud_flow(auth_client):
    create = auth_client.post(
        "/api/aufgaben",
        json={
            "title": "Angebot prüfen",
            "details": "Kunde möchte Rückruf",
            "due_date": "2099-12-31",
            "priority": "HIGH",
            "assigned_to": "max",
            "source_type": "doc",
            "source_ref": "doc-123",
        },
    )
    assert create.status_code == 201
    body = create.get_json()
    task_id = int(body["task"]["id"])
    assert body["task"]["priority"] == "HIGH"
    assert body["task"]["assigned_to"] == "max"
    assert body["task"]["source_ref"] == "doc-123"

    got = auth_client.get(f"/api/aufgaben/{task_id}")
    assert got.status_code == 200
    assert got.get_json()["task"]["title"] == "Angebot prüfen"

    updated = auth_client.patch(
        f"/api/aufgaben/{task_id}",
        json={"status": "DONE", "priority": "LOW", "assigned_to": "maria"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["task"]["status"] == "DONE"
    assert updated.get_json()["task"]["priority"] == "LOW"

    listing = auth_client.get("/api/aufgaben?status=DONE")
    assert listing.status_code == 200
    assert any(int(item["id"]) == task_id for item in listing.get_json()["items"])

    deleted = auth_client.delete(f"/api/aufgaben/{task_id}")
    assert deleted.status_code == 200

    missing = auth_client.get(f"/api/aufgaben/{task_id}")
    assert missing.status_code == 404


def test_aufgaben_summary_open_overdue_today(auth_client):
    auth_client.post(
        "/api/aufgaben",
        json={"title": "heute", "due_date": "2000-01-01", "priority": "MEDIUM"},
    )
    auth_client.post(
        "/api/aufgaben",
        json={"title": "offen ohne due", "priority": "LOW"},
    )

    summary = auth_client.get("/api/aufgaben/summary")
    assert summary.status_code == 200
    metrics = summary.get_json()["metrics"]
    assert set(metrics.keys()) >= {"tasks_open", "tasks_overdue", "tasks_today"}
    assert metrics["tasks_open"] >= 2
    assert metrics["tasks_overdue"] >= 1


def test_email_received_todo_creates_task_and_notification(auth_client):
    shared_services.notifications.clear()
    shared_services.publish(
        "email.received",
        {
            "tenant": "KUKANILEA",
            "subject": "TODO: Angebot finalisieren",
            "body": "Bitte bis Freitag fertigstellen",
            "message_id": "mail-1",
            "assigned_to": "team-a",
            "priority": "URGENT",
        },
    )

    listing = auth_client.get("/api/aufgaben")
    assert listing.status_code == 200
    items = listing.get_json()["items"]
    assert any(
        i["title"] == "Angebot finalisieren"
        and i["source_type"] == "email"
        and i["source_ref"] == "mail-1"
        and i["priority"] == "URGENT"
        for i in items
    )

    assert any(
        n["message"] == "Aufgabe aus E-Mail erstellt" and n["data"].get("source") == "email.received"
        for n in shared_services.notifications
    )
