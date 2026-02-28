from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app import core as legacy_core

from .logic import _tenant, automation_latest_run


def _today(day: str | None = None) -> str:
    if day:
        return str(day)
    return datetime.now(UTC).date().isoformat()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _table_exists(con, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


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

            has_claims = _table_exists(con, "lead_claims")
            has_events = _table_exists(con, "events")

            unclaimed = {"c": 0}
            expiring_soon = {"c": 0}
            if has_claims:
                unclaimed = con.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM leads l
                    WHERE l.tenant_id=?
                      AND NOT EXISTS (
                        SELECT 1
                        FROM lead_claims lc
                        WHERE lc.tenant_id=l.tenant_id
                          AND lc.lead_id=l.id
                          AND lc.released_at IS NULL
                          AND datetime(lc.claimed_until) >= datetime('now')
                      )
                    """,
                    (t,),
                ).fetchone() or {"c": 0}
                expiring_soon = con.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM lead_claims
                    WHERE tenant_id=?
                      AND released_at IS NULL
                      AND datetime(claimed_until) >= datetime('now')
                      AND datetime(claimed_until) <= datetime('now', '+30 minutes')
                    """,
                    (t,),
                ).fetchone() or {"c": 0}

            overdue_by_owner_rows = con.execute(
                """
                SELECT assigned_to, COUNT(*) AS c
                FROM leads
                WHERE tenant_id=?
                  AND assigned_to IS NOT NULL
                  AND TRIM(assigned_to) <> ''
                  AND response_due IS NOT NULL
                  AND datetime(response_due) < datetime('now')
                GROUP BY assigned_to
                ORDER BY c DESC, assigned_to ASC
                LIMIT 5
                """,
                (t,),
            ).fetchall()

            collisions = {"c": 0}
            if has_events:
                collisions = con.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM events
                    WHERE event_type='lead_claim_collision'
                      AND entity_type='lead'
                      AND datetime(ts) >= datetime('now','-1 day')
                      AND payload_json LIKE ?
                    """,
                    (f'%"tenant_id":"{t}"%',),
                ).fetchone() or {"c": 0}
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
        "unclaimed_leads_count": int((unclaimed and unclaimed["c"]) or 0),
        "claims_expiring_soon_count": int((expiring_soon and expiring_soon["c"]) or 0),
        "overdue_leads_by_owner": [
            {"owner": str(row["assigned_to"] or ""), "count": int(row["c"] or 0)}
            for row in overdue_by_owner_rows
        ],
        "claim_collisions_count": int((collisions and collisions["c"]) or 0),
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
