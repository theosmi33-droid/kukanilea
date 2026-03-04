from __future__ import annotations

from datetime import UTC, datetime

from app import core


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
