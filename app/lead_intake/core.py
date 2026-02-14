from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

LEAD_STATUSES = {"new", "contacted", "qualified", "lost", "won"}
LEAD_SOURCES = {"call", "email", "webform", "manual"}
CALL_DIRECTIONS = {"inbound", "outbound"}
APPOINTMENT_STATUSES = {"pending", "accepted", "declined", "rescheduled"}


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _ensure_writable() -> None:
    if _is_read_only():
        raise ValueError("read_only")


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _read_rows(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            rows = con.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def leads_create(
    tenant_id: str,
    source: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    subject: str,
    message: str,
    customer_id: str | None = None,
    notes: str | None = None,
    actor_user_id: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    src = legacy_core.normalize_component(source).lower()
    if src not in LEAD_SOURCES:
        raise ValueError("validation_error")
    lead_id = _new_id()
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> str:
        if customer_id:
            row = con.execute(
                "SELECT id FROM customers WHERE tenant_id=? AND id=?",
                (t, customer_id),
            ).fetchone()
            if not row:
                raise ValueError("not_found")

        con.execute(
            """
            INSERT INTO leads(
              id, tenant_id, status, source, customer_id,
              contact_name, contact_email, contact_phone,
              subject, message, notes, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                lead_id,
                t,
                "new",
                src,
                customer_id,
                legacy_core.normalize_component(contact_name),
                legacy_core.normalize_component(contact_email),
                legacy_core.normalize_component(contact_phone),
                legacy_core.normalize_component(subject),
                (message or "").strip(),
                (notes or "").strip(),
                now,
                now,
            ),
        )
        event_append(
            event_type="lead_created",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_create",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "status": "new",
                    "source": src,
                    "customer_id": customer_id,
                },
            },
            con=con,
        )
        return lead_id

    return _run_write_txn(_tx)


def leads_get(tenant_id: str, lead_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    rows = _read_rows(
        """
        SELECT id, tenant_id, status, source, customer_id, contact_name, contact_email,
               contact_phone, subject, message, notes, created_at, updated_at
        FROM leads
        WHERE tenant_id=? AND id=?
        LIMIT 1
        """,
        (t, lead_id),
    )
    return rows[0] if rows else None


def leads_list(
    tenant_id: str,
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    clauses = ["tenant_id=?"]
    params: list[Any] = [t]

    st = legacy_core.normalize_component(status).lower()
    if st:
        if st not in LEAD_STATUSES:
            raise ValueError("validation_error")
        clauses.append("status=?")
        params.append(st)

    src = legacy_core.normalize_component(source).lower()
    if src:
        if src not in LEAD_SOURCES:
            raise ValueError("validation_error")
        clauses.append("source=?")
        params.append(src)

    qq = legacy_core.normalize_component(q)
    if qq:
        clauses.append(
            "(LOWER(COALESCE(subject,'')) LIKE LOWER(?) OR LOWER(COALESCE(contact_name,'')) LIKE LOWER(?))"
        )
        params.extend([f"%{qq}%", f"%{qq}%"])

    where_sql = " AND ".join(clauses)
    return _read_rows(
        f"""
        SELECT id, tenant_id, status, source, customer_id, contact_name,
               contact_email, contact_phone, subject, message, notes,
               created_at, updated_at
        FROM leads
        WHERE {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [lim, off]),
    )


def leads_update_status(
    tenant_id: str,
    lead_id: str,
    new_status: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    status_norm = legacy_core.normalize_component(new_status).lower()
    if status_norm not in LEAD_STATUSES:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT status, source, customer_id FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = str(row["status"] or "")
        con.execute(
            "UPDATE leads SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
            (status_norm, _now_iso(), t, lead_id),
        )
        event_append(
            event_type="lead_status_updated",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_update_status",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "prev_status": prev,
                    "status": status_norm,
                    "source": str(row["source"] or ""),
                    "customer_id": row["customer_id"],
                },
            },
            con=con,
        )
        return None

    _run_write_txn(_tx)


def leads_add_note(
    tenant_id: str,
    lead_id: str,
    note_text: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    note = (note_text or "").strip()
    if not note:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT notes FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = (row["notes"] or "").strip()
        next_note = note if not prev else f"{prev}\n- {note}"
        con.execute(
            "UPDATE leads SET notes=?, updated_at=? WHERE tenant_id=? AND id=?",
            (next_note, _now_iso(), t, lead_id),
        )
        event_append(
            event_type="lead_note_added",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_add_note",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {"lead_id": lead_id, "note_added": True},
            },
            con=con,
        )
        return None

    _run_write_txn(_tx)


def call_logs_create(
    tenant_id: str,
    lead_id: str | None,
    caller_name: str,
    caller_phone: str,
    direction: str,
    duration_seconds: int | None,
    notes: str | None,
    actor_user_id: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    dir_norm = legacy_core.normalize_component(direction).lower()
    if dir_norm not in CALL_DIRECTIONS:
        raise ValueError("validation_error")
    call_id = _new_id()

    def _tx(con: sqlite3.Connection) -> str:
        if lead_id:
            row = con.execute(
                "SELECT id FROM leads WHERE tenant_id=? AND id=?",
                (t, lead_id),
            ).fetchone()
            if not row:
                raise ValueError("not_found")
        con.execute(
            """
            INSERT INTO call_logs(
              id, tenant_id, lead_id, caller_name, caller_phone,
              direction, duration_seconds, notes, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                call_id,
                t,
                lead_id,
                legacy_core.normalize_component(caller_name),
                legacy_core.normalize_component(caller_phone),
                dir_norm,
                int(duration_seconds) if duration_seconds is not None else None,
                (notes or "").strip(),
                _now_iso(),
            ),
        )
        event_append(
            event_type="call_log_created",
            entity_type="call_log",
            entity_id=entity_id_int(call_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/call_logs_create",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "call_log_id": call_id,
                    "lead_id": lead_id,
                    "direction": dir_norm,
                    "duration_seconds": int(duration_seconds or 0),
                },
            },
            con=con,
        )
        return call_id

    return _run_write_txn(_tx)


def call_logs_list(tenant_id: str, lead_id: str | None = None) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    if lead_id:
        return _read_rows(
            """
            SELECT id, tenant_id, lead_id, caller_name, caller_phone, direction,
                   duration_seconds, notes, created_at
            FROM call_logs
            WHERE tenant_id=? AND lead_id=?
            ORDER BY created_at DESC, id DESC
            """,
            (t, lead_id),
        )
    return _read_rows(
        """
        SELECT id, tenant_id, lead_id, caller_name, caller_phone, direction,
               duration_seconds, notes, created_at
        FROM call_logs
        WHERE tenant_id=?
        ORDER BY created_at DESC, id DESC
        LIMIT 200
        """,
        (t,),
    )


def appointment_requests_create(
    tenant_id: str,
    lead_id: str,
    requested_date: str | None,
    notes: str | None,
    actor_user_id: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    if requested_date:
        try:
            datetime.fromisoformat(str(requested_date))
        except Exception:
            raise ValueError("validation_error")
    req_id = _new_id()

    def _tx(con: sqlite3.Connection) -> str:
        row = con.execute(
            "SELECT id FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        now = _now_iso()
        con.execute(
            """
            INSERT INTO appointment_requests(
              id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                req_id,
                t,
                lead_id,
                str(requested_date) if requested_date else None,
                "pending",
                (notes or "").strip(),
                now,
                now,
            ),
        )
        event_append(
            event_type="appointment_request_created",
            entity_type="appointment_request",
            entity_id=entity_id_int(req_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/appointment_requests_create",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "appointment_request_id": req_id,
                    "lead_id": lead_id,
                    "status": "pending",
                },
            },
            con=con,
        )
        return req_id

    return _run_write_txn(_tx)


def appointment_requests_update_status(
    tenant_id: str,
    req_id: str,
    status: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    st = legacy_core.normalize_component(status).lower()
    if st not in APPOINTMENT_STATUSES:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT lead_id, status FROM appointment_requests WHERE tenant_id=? AND id=?",
            (t, req_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = str(row["status"] or "")
        con.execute(
            "UPDATE appointment_requests SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
            (st, _now_iso(), t, req_id),
        )
        event_append(
            event_type="appointment_request_status_updated",
            entity_type="appointment_request",
            entity_id=entity_id_int(req_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/appointment_requests_update_status",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "appointment_request_id": req_id,
                    "lead_id": str(row["lead_id"] or ""),
                    "prev_status": prev,
                    "status": st,
                },
            },
            con=con,
        )
        return None

    _run_write_txn(_tx)


def appointment_requests_get(tenant_id: str, req_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    rows = _read_rows(
        """
        SELECT id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
        FROM appointment_requests
        WHERE tenant_id=? AND id=?
        LIMIT 1
        """,
        (t, req_id),
    )
    return rows[0] if rows else None


def appointment_requests_list(
    tenant_id: str,
    lead_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    if lead_id:
        return _read_rows(
            """
            SELECT id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
            FROM appointment_requests
            WHERE tenant_id=? AND lead_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (t, lead_id, lim, off),
        )
    return _read_rows(
        """
        SELECT id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
        FROM appointment_requests
        WHERE tenant_id=?
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (t, lim, off),
    )


def lead_timeline(tenant_id: str, lead_id: str, limit: int = 100) -> dict[str, Any]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), 500))

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            events = con.execute(
                """
                SELECT id, ts, event_type, entity_type, entity_id, payload_json
                FROM events
                WHERE entity_id=?
                  AND entity_type IN ('lead','call_log','appointment_request')
                ORDER BY ts DESC, id DESC
                LIMIT ?
                """,
                (entity_id_int(lead_id), lim),
            ).fetchall()
            calls = con.execute(
                """
                SELECT id, lead_id, caller_name, direction, duration_seconds, created_at
                FROM call_logs
                WHERE tenant_id=? AND lead_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (t, lead_id, lim),
            ).fetchall()
            appts = con.execute(
                """
                SELECT id, lead_id, requested_date, status, created_at, updated_at
                FROM appointment_requests
                WHERE tenant_id=? AND lead_id=?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (t, lead_id, lim),
            ).fetchall()
        finally:
            con.close()

    out_events: list[dict[str, Any]] = []
    for row in events:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload_json") or "{}")
        except Exception:
            item["payload"] = {}
        out_events.append(item)

    return {
        "events": out_events,
        "call_logs": [dict(r) for r in calls],
        "appointment_requests": [dict(r) for r in appts],
    }


def appointment_request_to_ics(tenant_id: str, req_id: str) -> tuple[str, str]:
    item = appointment_requests_get(tenant_id, req_id)
    if not item:
        raise ValueError("not_found")

    now = datetime.now(timezone.utc)
    dtstamp = now.strftime("%Y%m%dT%H%M%SZ")
    requested = item.get("requested_date")
    dtstart_line = ""
    if requested:
        try:
            dt = datetime.fromisoformat(str(requested))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dtstart_line = f"DTSTART:{dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}\\r\\n"
        except Exception:
            pass
    if not dtstart_line:
        fallback = now + timedelta(days=1)
        dtstart_line = f"DTSTART:{fallback.strftime('%Y%m%dT%H%M%SZ')}\\r\\n"

    summary = f"Terminwunsch (Lead {str(item.get('lead_id') or '')[:8]})"
    description = f"Lead-ID: {item.get('lead_id') or ''}"
    ics = (
        "BEGIN:VCALENDAR\\r\\n"
        "VERSION:2.0\\r\\n"
        "PRODID:-//KUKANILEA//Lead Intake//DE\\r\\n"
        "BEGIN:VEVENT\\r\\n"
        f"UID:{req_id}@kukanilea.local\\r\\n"
        f"DTSTAMP:{dtstamp}\\r\\n"
        f"{dtstart_line}"
        f"SUMMARY:{summary}\\r\\n"
        f"DESCRIPTION:{description}\\r\\n"
        "END:VEVENT\\r\\n"
        "END:VCALENDAR\\r\\n"
    )
    return ics, f"appointment_{req_id}.ics"
