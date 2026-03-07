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


def test_aufgaben_due_date_normalized_and_overdue_detection_is_stable(auth_client):
    created = auth_client.post(
        "/api/aufgaben",
        json={
            "title": "Frist aus Upload",
            "due_date": "2030-03-04T12:13:14+00:00",
            "source_type": "upload",
        },
    )
    assert created.status_code == 201
    task_id = int(created.get_json()["task"]["id"])

    get_task = auth_client.get(f"/api/aufgaben/{task_id}")
    assert get_task.status_code == 200
    assert get_task.get_json()["task"]["due_date"] == "2030-03-04"

    invalid_update = auth_client.patch(
        f"/api/aufgaben/{task_id}",
        json={"due_date": "morgen irgendwann"},
    )
    assert invalid_update.status_code == 200
    assert invalid_update.get_json()["task"]["due_date"] is None


def test_aufgaben_status_transition_blocks_invalid_path(auth_client):
    created = auth_client.post(
        "/api/aufgaben",
        json={
            "title": "Statuspfad",
            "source_type": "messenger",
            "source_ref": "chat-77",
        },
    )
    assert created.status_code == 201
    task_id = int(created.get_json()["task"]["id"])

    done = auth_client.patch(f"/api/aufgaben/{task_id}", json={"status": "DONE"})
    assert done.status_code == 200
    assert done.get_json()["task"]["status"] == "DONE"

    blocked_invalid = auth_client.patch(
        f"/api/aufgaben/{task_id}",
        json={"status": "BLOCKED"},
    )
    assert blocked_invalid.status_code == 200
    assert blocked_invalid.get_json()["task"]["status"] == "DONE"

    reopened = auth_client.patch(f"/api/aufgaben/{task_id}", json={"status": "OPEN"})
    assert reopened.status_code == 200
    assert reopened.get_json()["task"]["status"] == "OPEN"


def test_intake_execute_creates_task_for_mail_messenger_upload_sources(auth_client):
    scenarios = [
        ("mail", "mail-thread-1", "Mail Aufgabe"),
        ("messenger", "chat-thread-1", "Messenger Follow-up"),
        ("upload", "upload-thread-1", "Upload Frist"),
    ]

    for source, thread_id, title in scenarios:
        normalized = auth_client.post(
            "/api/intake/normalize",
            json={
                "source": source,
                "thread_id": thread_id,
                "subject": title,
                "message": f"Bitte als Aufgabe erfassen: {title}",
                "due_date": "2031-01-15",
            },
        )
        assert normalized.status_code == 200
        envelope = normalized.get_json()["envelope"]

        executed = auth_client.post(
            "/api/intake/execute",
            json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
        )
        assert executed.status_code == 200
        assert executed.get_json()["status"] == "executed"

    listing = auth_client.get("/api/aufgaben")
    assert listing.status_code == 200
    items = listing.get_json()["items"]
    refs = {item.get("source_ref"): item for item in items}
    assert "mail-thread-1" in refs
    assert "chat-thread-1" in refs
    assert "upload-thread-1" in refs
