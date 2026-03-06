from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.eventlog import event_append
from app.modules.aufgaben import logic
from app.services.shared_services import shared_services


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    metrics = logic.summary(tenant=tenant)
    return {
        "status": "ok",
        "timestamp": _timestamp(),
        "metrics": {
            "tasks_open": metrics["open"],
            "tasks_overdue": metrics["overdue"],
            "tasks_today": metrics["today"],
        },
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": 1,
        "offline_safe": 1,
    }
    return payload, 200


def create_task(
    *,
    tenant: str,
    title: str,
    details: str = "",
    due_date: str | None = None,
    project_hint: str | None = None,
    calendar_hint: str | None = None,
    created_by: str = "system",
    source_ref: str = "",
    priority: str = "MEDIUM",
    assigned_to: str | None = None,
    source_type: str = "doc",
) -> dict[str, Any]:
    task = logic.create_task(
        tenant=tenant,
        title=title,
        details=details,
        due_date=due_date,
        priority=priority,
        assigned_to=assigned_to,
        source_type=source_type,
        source_ref=source_ref,
        created_by=created_by,
    )
    event_append(
        "intake_task_created",
        "task",
        int(task.get("id") or 0),
        {
            "tenant": tenant,
            "title": title,
            "source_ref": source_ref,
            "created_by": created_by,
            "project_hint": project_hint,
            "calendar_hint": calendar_hint,
        },
    )
    return {
        "task_id": int(task.get("id") or 0),
        "title": str(task.get("title") or title),
    }


def _handle_email_received(payload: dict[str, Any]) -> None:
    subject = str(payload.get("subject") or "").strip()
    if not subject.lower().startswith("todo:"):
        return

    tenant = str(payload.get("tenant") or "KUKANILEA")
    creator = str(payload.get("created_by") or "email-bot")
    task_title = subject.split(":", 1)[1].strip() or "E-Mail TODO"
    task = logic.create_task(
        tenant=tenant,
        title=task_title,
        details=str(payload.get("body") or "").strip(),
        due_date=payload.get("due_date"),
        priority=str(payload.get("priority") or "MEDIUM"),
        assigned_to=payload.get("assigned_to"),
        source_type="email",
        source_ref=str(payload.get("message_id") or payload.get("thread_id") or ""),
        created_by=creator,
    )
    shared_services.notify(
        "Aufgabe aus E-Mail erstellt",
        level="info",
        data={"tenant": tenant, "task_id": task.get("id"), "source": "email.received"},
    )


shared_services.subscribe("email.received", _handle_email_received)
