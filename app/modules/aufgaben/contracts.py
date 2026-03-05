from __future__ import annotations

from datetime import UTC, datetime

from app import core

CONTRACT_VERSION = "2026-03-05"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(_tenant: str) -> dict:
    task_list = getattr(core, "task_list", None)
    tasks = task_list() if callable(task_list) else []
    open_count = sum(1 for task in tasks if str(task.get("status", "")).lower() != "done") if tasks else 0
    status = "ok" if callable(task_list) else "degraded"
    warnings = [] if status == "ok" else ["tasks_backend_missing"]
    summary = {"tasks_total": len(tasks), "tasks_open": open_count, "contract_version": CONTRACT_VERSION}
    return {
        "tool": "aufgaben",
        "version": CONTRACT_VERSION,
        "status": status,
        "ts": _timestamp(),
        "summary": summary,
        "warnings": warnings,
        "links": [{"rel": "health", "href": "/api/aufgaben/health"}],
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
