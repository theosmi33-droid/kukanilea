from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import Config
from app.modules.kalender.contracts import parse_local_ics


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("datetime_value_required")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if len(raw) == 15 and "T" in raw:
        return datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    if len(raw) == 16 and raw.endswith("Z") and "T" in raw:
        return datetime.strptime(raw, "%Y%m%dT%H%MZ").replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fmt_dt(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ics_window(raw_event: dict[str, str]) -> TimeWindow | None:
    start_raw = str(raw_event.get("start_at") or "").strip()
    if not start_raw:
        return None
    end_raw = str(raw_event.get("end_at") or start_raw).strip()
    try:
        start = _parse_dt(start_raw)
        end = _parse_dt(end_raw)
    except ValueError:
        return None
    if end <= start:
        end = start + timedelta(minutes=30)
    return TimeWindow(start=start, end=end)


class CalendarStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or (Config.USER_DATA_ROOT / "calendar.sqlite3"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS calendar_events(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  description TEXT,
                  location TEXT,
                  start_at TEXT NOT NULL,
                  end_at TEXT NOT NULL,
                  source_type TEXT NOT NULL DEFAULT 'local',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS calendar_audit(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  action TEXT NOT NULL,
                  event_id INTEGER,
                  payload_json TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_calendar_events_tenant_start ON calendar_events(tenant_id, start_at);"
            )

    def _emit_audit(self, *, tenant_id: str, action: str, event_id: int | None, payload: dict[str, Any]) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO calendar_audit(ts, tenant_id, action, event_id, payload_json) VALUES (?,?,?,?,?)",
                (_utc_now_iso(), tenant_id, action, event_id, json.dumps(payload, ensure_ascii=False)),
            )

    def list_audit(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT ts, tenant_id, action, event_id, payload_json FROM calendar_audit WHERE tenant_id=? ORDER BY id",
                (tenant_id,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(str(row["payload_json"]) or "{}")
            out.append({"ts": row["ts"], "tenant_id": row["tenant_id"], "action": row["action"], "event_id": row["event_id"], "payload": payload})
        return out

    def create_event(self, *, tenant_id: str, title: str, start_at: str, end_at: str, description: str = "", location: str = "", created_by: str = "system") -> dict[str, Any]:
        start = _parse_dt(start_at)
        end = _parse_dt(end_at)
        if end <= start:
            raise ValueError("event_end_must_be_after_start")
        now = _utc_now_iso()
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO calendar_events(tenant_id, title, description, location, start_at, end_at, source_type, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (tenant_id, title.strip() or "Termin", description, location, _fmt_dt(start), _fmt_dt(end), "local", created_by, now, now),
            )
            event_id = int(cur.lastrowid)
            row = con.execute("SELECT * FROM calendar_events WHERE id=?", (event_id,)).fetchone()
        event = dict(row or {})
        self._emit_audit(tenant_id=tenant_id, action="calendar.create_event", event_id=event_id, payload={"title": event.get("title"), "start_at": event.get("start_at"), "end_at": event.get("end_at"), "created_by": created_by})
        return event

    def update_event(self, *, tenant_id: str, event_id: int, title: str | None = None, start_at: str | None = None, end_at: str | None = None, description: str | None = None, location: str | None = None, updated_by: str = "system") -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM calendar_events WHERE id=? AND tenant_id=? AND source_type='local'", (event_id, tenant_id)).fetchone()
            if not row:
                raise ValueError("event_not_found")
            current = dict(row)
            new_title = title if title is not None else str(current.get("title") or "")
            new_start = _parse_dt(start_at or str(current.get("start_at") or ""))
            new_end = _parse_dt(end_at or str(current.get("end_at") or ""))
            if new_end <= new_start:
                raise ValueError("event_end_must_be_after_start")
            new_description = description if description is not None else str(current.get("description") or "")
            new_location = location if location is not None else str(current.get("location") or "")
            con.execute(
                """
                UPDATE calendar_events
                SET title=?, description=?, location=?, start_at=?, end_at=?, updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (new_title, new_description, new_location, _fmt_dt(new_start), _fmt_dt(new_end), _utc_now_iso(), event_id, tenant_id),
            )
            updated = con.execute("SELECT * FROM calendar_events WHERE id=?", (event_id,)).fetchone()
        event = dict(updated or {})
        self._emit_audit(tenant_id=tenant_id, action="calendar.update_event", event_id=event_id, payload={"updated_by": updated_by, "fields": {"title": title, "start_at": start_at, "end_at": end_at, "description": description, "location": location}})
        return event

    def _busy_windows(self, *, tenant_id: str, window_start: datetime, window_end: datetime, ics_texts: list[str] | None = None) -> list[TimeWindow]:
        busy: list[TimeWindow] = []
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT start_at, end_at FROM calendar_events
                WHERE tenant_id=? AND end_at > ? AND start_at < ?
                ORDER BY start_at ASC, id ASC
                """,
                (tenant_id, _fmt_dt(window_start), _fmt_dt(window_end)),
            ).fetchall()
        for row in rows:
            busy.append(TimeWindow(start=_parse_dt(str(row["start_at"])), end=_parse_dt(str(row["end_at"]))))

        for text in (ics_texts or []):
            for event in parse_local_ics(text):
                window = _ics_window(event)
                if not window:
                    continue
                if window.end <= window_start or window.start >= window_end:
                    continue
                busy.append(window)

        return sorted(busy, key=lambda item: (item.start, item.end))

    def find_free_slot(
        self,
        *,
        tenant_id: str,
        window_start: str,
        window_end: str,
        duration_minutes: int = 30,
        granularity_minutes: int = 15,
        ics_texts: list[str] | None = None,
    ) -> dict[str, Any]:
        start = _parse_dt(window_start)
        end = _parse_dt(window_end)
        if end <= start:
            raise ValueError("window_end_must_be_after_start")
        duration = timedelta(minutes=max(1, int(duration_minutes)))
        step = timedelta(minutes=max(1, int(granularity_minutes)))
        busy = self._busy_windows(tenant_id=tenant_id, window_start=start, window_end=end, ics_texts=ics_texts)

        candidate = start
        while candidate + duration <= end:
            conflict: TimeWindow | None = None
            for window in busy:
                if candidate < window.end and (candidate + duration) > window.start:
                    conflict = window
                    break
            if conflict is None:
                return {
                    "status": "ok",
                    "start_at": _fmt_dt(candidate),
                    "end_at": _fmt_dt(candidate + duration),
                    "duration_minutes": int(duration.total_seconds() // 60),
                    "source": "local+ics" if ics_texts else "local",
                }
            candidate = max(candidate + step, conflict.end)
        return {"status": "no_slot", "reason": "no_free_slot_in_window"}
