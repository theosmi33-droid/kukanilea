from __future__ import annotations

from datetime import UTC, datetime

from app import core

CONTRACT_VERSION = "2026-03-05"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    time_entry_list = getattr(core, "time_entry_list", None)
    entries = time_entry_list(tenant=tenant) if callable(time_entry_list) else []
    running = sum(1 for entry in entries if not entry.get("ended_at")) if entries else 0
    status = "ok" if callable(time_entry_list) else "degraded"
    return {
        "tool": "zeiterfassung",
        "version": CONTRACT_VERSION,
        "status": status,
        "ts": _timestamp(),
        "summary": {
            "entries": len(entries),
            "running": running,
            "contract_version": CONTRACT_VERSION,
        },
        "warnings": [] if status == "ok" else ["time_tracking_unavailable"],
        "links": [{"rel": "health", "href": "/api/zeiterfassung/health"}],
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
