from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.config import Config
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

ACTIVATION_MILESTONES = (
    "first_login",
    "first_customer",
    "first_document",
    "first_task",
    "first_ai_summary",
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(str(_core_db_path()), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(math.ceil((p / 100.0) * len(ordered))))
    return int(ordered[rank - 1])


def _parse_iso(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except Exception:
        return None


def record_activation_milestone(
    *,
    tenant_id: str,
    actor_user_id: str,
    milestone: str,
    source: str,
    request_id: str = "",
    entity_ref: str = "",
) -> bool:
    tenant = str(tenant_id or "").strip()
    actor = str(actor_user_id or "").strip()
    mstone = str(milestone or "").strip().lower()
    src = str(source or "").strip()
    if not tenant or not actor or not src:
        raise ValueError("validation_error")
    if mstone not in ACTIVATION_MILESTONES:
        raise ValueError("validation_error")

    con = _open_db()
    try:
        row = con.execute(
            """
            SELECT id
            FROM events
            WHERE event_type='activation_milestone'
              AND payload_json LIKE ?
              AND payload_json LIKE ?
              AND payload_json LIKE ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (
                f'%"tenant_id":"{tenant}"%',
                f'%"actor_user_id":"{actor}"%',
                f'%"milestone":"{mstone}"%',
            ),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        con.close()

    if row:
        return False

    event_append(
        event_type="activation_milestone",
        entity_type="activation",
        entity_id=entity_id_int(f"{tenant}:{actor}:{mstone}"),
        payload={
            "tenant_id": tenant,
            "actor_user_id": actor,
            "milestone": mstone,
            "source": src,
            "request_id": str(request_id or "").strip(),
            "entity_ref": str(entity_ref or "").strip(),
        },
    )
    return True


def build_activation_report(
    tenant_id: str,
    *,
    limit_users: int = 200,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("validation_error")

    con = _open_db()
    try:
        rows = con.execute(
            """
            SELECT id, ts, payload_json
            FROM events
            WHERE event_type='activation_milestone'
            ORDER BY id ASC
            LIMIT 5000
            """
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        con.close()

    users: dict[str, dict[str, str]] = {}
    for row in rows:
        payload_raw = str(row["payload_json"] or "{}")
        try:
            payload = json.loads(payload_raw)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("tenant_id") or "").strip() != tenant:
            continue
        actor = str(payload.get("actor_user_id") or "").strip()
        milestone = str(payload.get("milestone") or "").strip().lower()
        if not actor or milestone not in ACTIVATION_MILESTONES:
            continue
        ts = str(row["ts"] or "").strip()
        if not ts:
            continue
        user_map = users.setdefault(actor, {})
        prev = user_map.get(milestone)
        if not prev or ts < prev:
            user_map[milestone] = ts

    user_items: list[dict[str, Any]] = []
    durations: list[int] = []
    target_seconds = 600
    target_met_count = 0

    for user_id in sorted(users.keys())[: max(1, min(int(limit_users), 1000))]:
        milestones = users[user_id]
        completed = all(key in milestones for key in ACTIVATION_MILESTONES)
        duration_seconds: int | None = None

        first_login_dt = _parse_iso(milestones.get("first_login") or "")
        if completed and first_login_dt is not None:
            max_dt: datetime | None = None
            for key in ACTIVATION_MILESTONES:
                dt = _parse_iso(milestones.get(key) or "")
                if dt is None:
                    max_dt = None
                    break
                if max_dt is None or dt > max_dt:
                    max_dt = dt
            if max_dt is not None:
                duration_seconds = max(
                    0, int((max_dt - first_login_dt).total_seconds())
                )
                durations.append(duration_seconds)
                if duration_seconds <= target_seconds:
                    target_met_count += 1

        user_items.append(
            {
                "user_id": user_id,
                "completed": completed,
                "time_to_first_workflow_seconds": duration_seconds,
                "milestones": {
                    key: str(milestones.get(key) or "") for key in ACTIVATION_MILESTONES
                },
            }
        )

    count = len(durations)
    average = int(sum(durations) / count) if count else None

    return {
        "generated_at": _now_iso(),
        "tenant_id": tenant,
        "milestones": list(ACTIVATION_MILESTONES),
        "target_seconds": target_seconds,
        "totals": {
            "users_seen": len(user_items),
            "users_completed": count,
            "target_met_count": target_met_count,
            "target_met_rate": round((target_met_count / count), 4) if count else 0.0,
        },
        "time_to_first_workflow_seconds": {
            "count": count,
            "min": min(durations) if count else None,
            "max": max(durations) if count else None,
            "avg": average,
            "p50": _percentile(durations, 50.0),
            "p95": _percentile(durations, 95.0),
        },
        "users": user_items,
    }
