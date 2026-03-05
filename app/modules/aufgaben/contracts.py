from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app import core
from app.eventlog import event_append


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(_tenant: str) -> dict:
    task_list = getattr(core, "task_list", None)
    tasks = task_list() if callable(task_list) else []
    open_count = sum(1 for task in tasks if str(task.get("status", "")).lower() != "done") if tasks else 0
    return {
        "status": "ok" if callable(task_list) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "tasks_total": len(tasks),
            "tasks_open": open_count,
        },
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": int(payload["status"] == "ok"),
        "offline_safe": 1,
    }
    code = 200 if payload["status"] in {"ok", "degraded"} else 503
    return payload, code


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
) -> dict[str, Any]:
    task_id = core.task_create(
        tenant=tenant,
        severity="INFO",
        task_type="INTAKE",
        title=title,
        details=details,
        token=source_ref,
        meta={
            "due_date": due_date,
            "project_hint": project_hint,
            "calendar_hint": calendar_hint,
        },
        created_by=created_by,
    )
    event_append(
        "intake_task_created",
        "task",
        int(task_id),
        {
            "tenant": tenant,
            "title": title,
            "source_ref": source_ref,
            "created_by": created_by,
        },
    )
    return {"task_id": int(task_id), "title": title}
