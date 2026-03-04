from __future__ import annotations

from datetime import UTC, datetime

from app import core


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    reminders_due = getattr(core, "knowledge_calendar_reminders_due", None)
    reminders = reminders_due(tenant) if callable(reminders_due) else []
    return {
        "status": "ok" if callable(reminders_due) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "due_reminders": len(reminders),
            "ics_export": 1,
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
