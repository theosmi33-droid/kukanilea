from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
import re
from pathlib import Path
from typing import Any

from app.contracts.tool_contracts import build_contract_response
from app.config import Config

SYNC_FLAG_ENV = "KUKANILEA_KALENDER_SYNC_ENABLED"
_LOCAL_QUEUE_NAME = "kalender_sync_queue.jsonl"
_SUBSCRIBERS: dict[str, bool] = {}
_SUBSCRIBERS_LOCK = threading.Lock()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _sync_enabled() -> bool:
    return str(os.environ.get(SYNC_FLAG_ENV, "0")).strip().lower() in {"1", "true", "yes", "on"}


def _sync_queue_path() -> Path:
    root = Path(Config.USER_DATA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root / _LOCAL_QUEUE_NAME


def _queue_sync(action: str, payload: dict[str, Any]) -> None:
    record = {
        "id": str(uuid.uuid4()),
        "action": action,
        "payload": payload,
        "created_at": _timestamp(),
        "sync_enabled": _sync_enabled(),
    }
    with _sync_queue_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _mirror_manual_event_to_knowledge(
    *,
    tenant: str,
    created_by: str,
    title: str,
    starts_at: str,
    ends_at: str,
    reminder_minutes: int,
) -> None:
    """
    Backward-compatibility bridge for existing consumers that still read
    appointment events from knowledge_calendar_events_list.
    """
    try:
        from app.knowledge.ics_source import knowledge_calendar_event_create

        knowledge_calendar_event_create(
            tenant,
            created_by,
            title=title,
            start_at=starts_at,
            end_at=ends_at,
            kind="appointment",
            reminder_minutes=reminder_minutes,
        )
    except Exception:
        # Keep local kalender_events as source-of-truth even if mirror write fails.
        return


def _db() -> sqlite3.Connection:
    path = Path(Config.CORE_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS kalender_events (
            event_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            title TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            reminder_minutes INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'calendar.api',
            created_by TEXT NOT NULL DEFAULT 'system',
            updated_by TEXT NOT NULL DEFAULT 'system',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_kalender_tenant_start ON kalender_events(tenant_id, starts_at);")
    return con


def _db_pragmas_offline_safe() -> int:
    try:
        con = _db()
        try:
            journal = str(con.execute("PRAGMA journal_mode;").fetchone()[0]).lower()
            sync = str(con.execute("PRAGMA synchronous;").fetchone()[0]).lower()
            return int(journal == "wal" and sync in {"1", "normal"})
        finally:
            con.close()
    except Exception:
        return 0


def _ensure_subscribers_registered() -> None:
    with _SUBSCRIBERS_LOCK:
        if _SUBSCRIBERS.get("document.processed"):
            return
        _SUBSCRIBERS["document.processed"] = True


def _events_list(tenant: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    con = _db()
    try:
        rows = con.execute(
            """
            SELECT event_id, title, starts_at, ends_at, reminder_minutes, source
            FROM kalender_events
            WHERE tenant_id=? AND starts_at>=? AND starts_at<=?
            ORDER BY starts_at ASC, title ASC
            """,
            (tenant, _iso(start), _iso(end)),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def _reminders_due(tenant: str, now: datetime, within_minutes: int = 60) -> list[dict[str, Any]]:
    events = _events_list(tenant, now - timedelta(days=1), now + timedelta(days=7))
    horizon = now + timedelta(minutes=max(1, min(int(within_minutes), 10080)))
    out: list[dict[str, Any]] = []
    for ev in events:
        start_dt = _parse_iso(str(ev.get("starts_at") or ""))
        if not start_dt:
            continue
        minutes = max(0, min(int(ev.get("reminder_minutes", 0) or 0), 10080))
        remind_at = start_dt - timedelta(minutes=minutes)
        if now <= remind_at <= horizon:
            out.append(
                {
                    "event_id": ev["event_id"],
                    "title": ev["title"],
                    "start_at": ev["starts_at"],
                    "remind_at": _iso(remind_at),
                    "source": ev["source"],
                }
            )
    out.sort(key=lambda x: str(x.get("remind_at", "")))
    return out


def _find_conflicts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for ev in events:
        start = _parse_iso(str(ev.get("starts_at", "")))
        end = _parse_iso(str(ev.get("ends_at", ""))) or start
        if not start or not end:
            continue
        if end < start:
            end = start
        parsed.append((start, end, ev))
    parsed.sort(key=lambda row: row[0])
    conflicts: list[dict[str, Any]] = []
    for idx, (start_a, end_a, ev_a) in enumerate(parsed):
        for start_b, end_b, ev_b in parsed[idx + 1 :]:
            if start_b >= end_a:
                break
            if start_b < end_a and end_b > start_a:
                conflicts.append(
                    {
                        "event_id": str(ev_a.get("event_id") or ""),
                        "with_event_id": str(ev_b.get("event_id") or ""),
                        "title": str(ev_a.get("title") or ""),
                        "with_title": str(ev_b.get("title") or ""),
                        "overlap_start": _iso(max(start_a, start_b)),
                        "overlap_end": _iso(min(end_a, end_b)),
                    }
                )
    return conflicts


def handle_document_processed_event(tenant: str, event: dict[str, Any]) -> dict[str, Any]:
    deadlines = event.get("deadlines") if isinstance(event.get("deadlines"), list) else []
    created: list[dict[str, Any]] = []
    for item in deadlines:
        due = str(item.get("due_date") or item.get("start_at") or "").strip()
        title = str(item.get("title") or item.get("summary") or "Document deadline").strip() or "Document deadline"
        if due:
            created.append(
                create_event(
                    tenant=tenant,
                    title=title,
                    starts_at=due,
                    created_by=str(event.get("actor") or "eventbus"),
                    reminder_minutes=int(item.get("reminder_minutes") or 24 * 60),
                    source="document.processed",
                )
            )
    return {"created": created, "count": len(created)}


def build_summary(tenant: str) -> dict:
    _ensure_subscribers_registered()
    now = datetime.now(UTC)
    events = _events_list(tenant, now, now + timedelta(days=7))
    conflicts = _find_conflicts(events)
    reminders = _reminders_due(tenant, now)
    payload = build_contract_response(
        tool="kalender",
        status="ok",
        metrics={
            "events_next_7_days": len(events),
            "conflicts": len(conflicts),
            "due_reminders": len(reminders),
            "ics_export": 1,
            "sync_enabled": int(_sync_enabled()),
        },
        details={
            "source": "kalender.events",
            "window_days": 7,
            "events_next_7_days": events,
            "conflicts": conflicts,
            "reminders_due": reminders,
        },
        tenant=tenant,
    )
    # Backward compatibility: legacy consumers read these fields at top-level.
    payload["window_days"] = 7
    payload["events_next_7_days"] = events
    payload["conflicts"] = conflicts
    payload["reminders_due"] = reminders
    return payload


def build_health(tenant: str) -> tuple[dict, int]:
    summary = build_summary(tenant)
    return build_health_response(
        tool="kalender",
        status=summary["status"],
        metrics=summary["metrics"],
        details={
            **(summary.get("details") or {}),
            "offline_persistence": bool(_db_pragmas_offline_safe()),
        },
        tenant=tenant,
        degraded_reason=summary.get("degraded_reason", ""),
        checks={
            "summary_contract": True,
            "backend_ready": True,
            "offline_safe": True,
        },
    )


def _ics_unescape(value: str) -> str:
    return (
        (value or "")
        .replace(r"\n", "\n")
        .replace(r"\N", "\n")
        .replace(r"\;", ";")
        .replace(r"\,", ",")
        .replace(r"\\", "\\")
        .strip()
    )


def _ics_escape(value: str) -> str:
    return (
        (value or "")
        .replace("\\", r"\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", r"\n")
        .replace(";", r"\;")
        .replace(",", r"\,")
    )


def _ics_fold(line: str, width: int = 72) -> list[str]:
    if len(line) <= width:
        return [line]
    out = [line[:width]]
    rest = line[width:]
    while rest:
        out.append(f" {rest[: width - 1]}")
        rest = rest[width - 1 :]
    return out


def parse_local_ics(raw_ics: str) -> list[dict[str, str]]:
    text = (raw_ics or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    unfolded: list[str] = []
    for line in lines:
        if (line.startswith(" ") or line.startswith("\t")) and unfolded:
            unfolded[-1] = f"{unfolded[-1]}{line[1:]}"
        else:
            unfolded.append(line)

    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    in_event = False
    for line in unfolded:
        upper = line.strip().upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            in_event = True
            continue
        if upper == "END:VEVENT":
            if in_event and current.get("start_at"):
                events.append(current)
            in_event = False
            current = {}
            continue
        if not in_event or ":" not in line:
            continue

        left, value = line.split(":", 1)
        key = left.split(";", 1)[0].strip().upper()
        if key == "SUMMARY":
            current["title"] = _ics_unescape(value)
        elif key == "DTSTART":
            current["start_at"] = value.strip()
        elif key == "DTEND":
            current["end_at"] = value.strip()
        elif key == "UID":
            current["uid"] = _ics_unescape(value)
        elif key == "DESCRIPTION":
            current["description"] = _ics_unescape(value)
        elif key == "LOCATION":
            current["location"] = _ics_unescape(value)
    return events


def render_local_ics(events: Iterable[dict[str, str]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KUKANILEA//Calendar Local//DE",
        "CALSCALE:GREGORIAN",
    ]
    now_utc = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for idx, event in enumerate(events, start=1):
        start_at = str(event.get("start_at") or "").strip()
        if not start_at:
            continue
        end_at = str(event.get("end_at") or start_at).strip()
        uid = str(event.get("uid") or f"local-{idx}@kukanilea").strip()
        title = _ics_escape(str(event.get("title") or "Termin"))

        block = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{start_at}",
            f"DTEND:{end_at}",
            f"SUMMARY:{title}",
        ]
        description = str(event.get("description") or "").strip()
        if description:
            block.append(f"DESCRIPTION:{_ics_escape(description)}")
        location = str(event.get("location") or "").strip()
        if location:
            block.append(f"LOCATION:{_ics_escape(location)}")
        block.append("END:VEVENT")
        for entry in block:
            lines.extend(_ics_fold(entry))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_appointment_proposal(*, lead: str | None, project: str | None, starts_at: str | None) -> dict:
    lead_clean = re.sub(r"\s+", " ", str(lead or "")).strip()
    project_clean = re.sub(r"\s+", " ", str(project or "")).strip()
    if project_clean and lead_clean:
        title = f"{project_clean}: {lead_clean}"
    else:
        title = project_clean or lead_clean or "Termin"
    return {
        "type": "create_appointment",
        "mode": "proposal",
        "title": title[:180],
        "starts_at": str(starts_at or "").strip() or None,
        "requires_confirm": True,
    }


def create_event(
    *,
    tenant: str,
    title: str,
    starts_at: str,
    created_by: str = "system",
    ends_at: str | None = None,
    reminder_minutes: int = 0,
    source: str = "calendar.api",
) -> dict:
    event_id = str(uuid.uuid4())
    now = _timestamp()
    payload = {
        "event_id": event_id,
        "title": title,
        "starts_at": starts_at,
        "ends_at": str(ends_at or starts_at),
        "reminder_minutes": max(0, min(int(reminder_minutes), 10080)),
        "source": source,
    }
    con = _db()
    try:
        con.execute(
            """
            INSERT INTO kalender_events(event_id, tenant_id, title, starts_at, ends_at, reminder_minutes, source, created_by, updated_by, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payload["event_id"],
                tenant,
                payload["title"],
                payload["starts_at"],
                payload["ends_at"],
                payload["reminder_minutes"],
                payload["source"],
                created_by,
                created_by,
                now,
                now,
            ),
        )
        con.commit()
    finally:
        con.close()
    _queue_sync("event.create", {"tenant": tenant, **payload})
    _mirror_manual_event_to_knowledge(
        tenant=tenant,
        created_by=created_by,
        title=payload["title"],
        starts_at=payload["starts_at"],
        ends_at=payload["ends_at"],
        reminder_minutes=payload["reminder_minutes"],
    )
    return payload


def update_event(
    *,
    tenant: str,
    event_id: str,
    updated_by: str = "system",
    title: str | None = None,
    starts_at: str | None = None,
    ends_at: str | None = None,
    reminder_minutes: int | None = None,
) -> dict:
    con = _db()
    try:
        row = con.execute(
            "SELECT * FROM kalender_events WHERE tenant_id=? AND event_id=?",
            (tenant, event_id),
        ).fetchone()
        if not row:
            raise ValueError("event_not_found")
        rowd = dict(row)
        payload = {
            "event_id": event_id,
            "title": str(title if title is not None else rowd["title"]),
            "starts_at": str(starts_at if starts_at is not None else rowd["starts_at"]),
            "ends_at": str(ends_at if ends_at is not None else rowd["ends_at"]),
            "reminder_minutes": int(reminder_minutes if reminder_minutes is not None else rowd["reminder_minutes"]),
        }
        con.execute(
            """
            UPDATE kalender_events
            SET title=?, starts_at=?, ends_at=?, reminder_minutes=?, updated_by=?, updated_at=?
            WHERE tenant_id=? AND event_id=?
            """,
            (
                payload["title"],
                payload["starts_at"],
                payload["ends_at"],
                payload["reminder_minutes"],
                updated_by,
                _timestamp(),
                tenant,
                event_id,
            ),
        )
        con.commit()
    finally:
        con.close()
    _queue_sync("event.update", {"tenant": tenant, **payload})
    return payload


def propose_invitation(*, tenant: str, title: str, starts_at: str, attendees: list[str]) -> dict:
    return {
        "type": "create_invitation",
        "tenant": tenant,
        "title": title,
        "starts_at": starts_at,
        "attendees": [a for a in attendees if str(a).strip()],
        "status": "proposal",
        "requires_confirm": True,
    }


def create_invitation(
    *,
    tenant: str,
    title: str,
    starts_at: str,
    attendees: list[str],
    confirm: bool = False,
) -> dict:
    if not confirm:
        return {
            "ok": False,
            "status": "blocked",
            "error": "explicit_confirm_required",
            "requires_confirm": True,
            "proposal": propose_invitation(tenant=tenant, title=title, starts_at=starts_at, attendees=attendees),
        }
    payload = {
        "ok": True,
        "status": "queued",
        "title": title,
        "starts_at": starts_at,
        "attendees": [a for a in attendees if str(a).strip()],
    }
    _queue_sync("invitation.create", {"tenant": tenant, **payload})
    return payload
