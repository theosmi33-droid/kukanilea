from __future__ import annotations

from datetime import UTC, datetime

from app import core

CONTRACT_VERSION = "2026-03-05"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    reminders_due = getattr(core, "knowledge_calendar_reminders_due", None)
    reminders = reminders_due(tenant) if callable(reminders_due) else []
    status = "ok" if callable(reminders_due) else "degraded"
    warnings = [] if status == "ok" else ["calendar_source_missing"]
    return {
        "tool": "kalender",
        "version": CONTRACT_VERSION,
        "status": status,
        "ts": _timestamp(),
        "summary": {
            "due_reminders": len(reminders),
            "ics_export": True,
            "contract_version": CONTRACT_VERSION,
        },
        "warnings": warnings,
        "links": [{"rel": "health", "href": "/api/kalender/health"}],
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["summary"] = {
        **payload.get("summary", {}),
        "checks": {
            "summary_contract": True,
            "backend_ready": payload["status"] == "ok",
            "offline_safe": True,
        },
    }
    code = 200 if payload["status"] == "ok" else 503
    return payload, code
