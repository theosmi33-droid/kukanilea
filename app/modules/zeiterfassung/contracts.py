from __future__ import annotations

from app.contracts.tool_contracts import build_contract_response
from app import core
from app.core import logic as core_logic


def build_summary(tenant: str) -> dict:
    time_entry_list = getattr(core, "time_entry_list", None)
    entries = (
        time_entry_list(tenant_id=tenant, limit=500)
        if callable(time_entry_list)
        else []
    )
    running = sum(1 for entry in entries if not entry.get("end_at")) if entries else 0
    status = "ok" if callable(time_entry_list) else "degraded"
    degraded_reason = "time_tracking_unavailable" if status == "degraded" else ""
    return build_contract_response(
        tool="time",
        status=status,
        degraded_reason=degraded_reason,
        metrics={
            "entries": len(entries),
            "running": running,
        },
        details={
            "source": "core.time_entry_list",
        },
        tenant=tenant,
    )


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
    offline_persistence = bool(_offline_persistence_ready())
    payload["metrics"] = {
        **(payload.get("metrics") or {}),
        "offline_persistence": int(offline_persistence),
    }
    payload["details"] = {
        **(payload.get("details") or {}),
        "checks": {
            "summary_contract": True,
            "backend_ready": payload.get("status") == "ok",
            "offline_safe": True,
        },
        "offline_persistence": offline_persistence,
    }
    code = 200 if payload["status"] in {"ok", "degraded"} else 503
    return payload, code
