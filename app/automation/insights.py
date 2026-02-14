from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import kukanilea_core_v3_fixed as legacy_core

from .core import _tenant, automation_latest_run


def _today(day: str | None = None) -> str:
    if day:
        return str(day)
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_daily_insights(tenant_id: str, day_yyyy_mm_dd: str) -> dict[str, Any]:
    t = _tenant(tenant_id)
    day = _today(day_yyyy_mm_dd)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            leads_new_24h = con.execute(
                "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND datetime(created_at) >= datetime('now','-1 day')",
                (t,),
            ).fetchone()
            leads_overdue = con.execute(
                "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND response_due IS NOT NULL AND datetime(response_due) < datetime('now')",
                (t,),
            ).fetchone()
            leads_screening = con.execute(
                "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND status='screening'",
                (t,),
            ).fetchone()
            leads_unassigned_high = con.execute(
                "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND priority='high' AND (assigned_to IS NULL OR assigned_to='')",
                (t,),
            ).fetchone()
            tasks_open = con.execute(
                "SELECT COUNT(*) AS c FROM tasks WHERE tenant=? AND status='OPEN'",
                (t,),
            ).fetchone()
        finally:
            con.close()

    latest = automation_latest_run(t) or {}
    return {
        "day": day,
        "leads_new_24h_count": int((leads_new_24h and leads_new_24h["c"]) or 0),
        "leads_overdue_count": int((leads_overdue and leads_overdue["c"]) or 0),
        "leads_screening_count": int((leads_screening and leads_screening["c"]) or 0),
        "leads_unassigned_high_priority_count": int(
            (leads_unassigned_high and leads_unassigned_high["c"]) or 0
        ),
        "tasks_open_count": int((tasks_open and tasks_open["c"]) or 0),
        "latest_run_status": str(latest.get("status") or "none"),
        "latest_run_actions_executed": int(latest.get("actions_executed") or 0),
    }


def get_or_build_daily_insights(
    tenant_id: str, day: str | None = None
) -> dict[str, Any]:
    t = _tenant(tenant_id)
    d = _today(day)

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            row = con.execute(
                "SELECT payload_json, generated_at FROM daily_insights_cache WHERE tenant_id=? AND day=?",
                (t, d),
            ).fetchone()
            if row:
                payload = json.loads(str(row["payload_json"] or "{}"))
                return {
                    "day": d,
                    "generated_at": str(row["generated_at"]),
                    "payload": payload,
                    "cached": True,
                }
        finally:
            con.close()

    payload = generate_daily_insights(t, d)
    gen_at = _now_iso()
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            con.execute(
                "INSERT OR REPLACE INTO daily_insights_cache(tenant_id, day, payload_json, generated_at) VALUES (?,?,?,?)",
                (
                    t,
                    d,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    gen_at,
                ),
            )
            con.commit()
        finally:
            con.close()
    return {"day": d, "generated_at": gen_at, "payload": payload, "cached": False}
