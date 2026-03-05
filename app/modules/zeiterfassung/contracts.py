from __future__ import annotations

from datetime import UTC, datetime

from app import core
from app.core import logic as core_logic


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    time_entry_list = getattr(core, "time_entry_list", None)
    entries = (
        time_entry_list(tenant_id=tenant, limit=500)
        if callable(time_entry_list)
        else []
    )
    running = sum(1 for entry in entries if not entry.get("end_at")) if entries else 0
    return {
        "status": "ok" if callable(time_entry_list) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "entries": len(entries),
            "running": running,
        },
    }


def _offline_persistence_ready() -> int:
    db_fn = getattr(core_logic, "_db", None)
    if not callable(db_fn):
        return 0
    try:
        con = db_fn()
        try:
            journal = str(con.execute("PRAGMA journal_mode;").fetchone()[0]).lower()
            sync = str(con.execute("PRAGMA synchronous;").fetchone()[0]).lower()
            return int(journal == "wal" and sync in {"1", "normal"})
        finally:
            con.close()
    except Exception:
        return 0


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": int(payload["status"] == "ok"),
        "offline_safe": 1,
        "offline_persistence": _offline_persistence_ready(),
    }
    code = 200 if payload["status"] in {"ok", "degraded"} else 503
    return payload, code
