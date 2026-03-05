from __future__ import annotations

from datetime import UTC, datetime

from app import core


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    time_entry_list = getattr(core, "time_entry_list", None)
    entries = time_entry_list(tenant=tenant) if callable(time_entry_list) else []
    running = sum(1 for entry in entries if not entry.get("ended_at")) if entries else 0
    total_duration_seconds = sum(int(entry.get("duration_seconds") or 0) for entry in entries)
    billable_basis_seconds = sum(
        int(entry.get("duration_seconds") or 0)
        for entry in entries
        if str(entry.get("approval_status") or "").upper() in {"APPROVED", "READY"}
    )
    return {
        "status": "ok" if callable(time_entry_list) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "entries": len(entries),
            "running": running,
            "total_duration_seconds": total_duration_seconds,
            "billable_basis_seconds": billable_basis_seconds,
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
