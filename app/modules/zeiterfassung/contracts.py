from __future__ import annotations

from datetime import UTC, datetime

from app import core


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    time_entry_list = getattr(core, "time_entry_list", None)
    entries = time_entry_list(tenant=tenant) if callable(time_entry_list) else []
    running = sum(1 for entry in entries if not entry.get("ended_at")) if entries else 0
    return {
        "status": "ok" if callable(time_entry_list) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "entries": len(entries),
            "running": running,
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
