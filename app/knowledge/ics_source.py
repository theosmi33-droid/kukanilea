from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from flask import current_app, has_app_context

from app import core as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

from .core import knowledge_policy_get

MAX_ICS_BYTES = 256 * 1024
MAX_EVENTS_PARSED = 10
MAX_CHUNKS_WRITTEN = 50
MAX_LINE_LEN = 2000
MAX_FIELD_LEN = 240

IGNORE_KEYS = {
    "ATTENDEE",
    "ORGANIZER",
    "DESCRIPTION",
    "COMMENT",
    "CONTACT",
    "ATTACH",
    "URL",
    "RRULE",
}
ALLOWED_KEYS = {"DTSTART", "DTEND", "SUMMARY", "LOCATION"}

DATE_ONLY_RE = re.compile(r"^\d{8}$")
DATE_TIME_RE = re.compile(r"^\d{8}T\d{6}$")
DATE_TIME_Z_RE = re.compile(r"^\d{8}T\d{6}Z$")


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _db() -> sqlite3.Connection:
    return legacy_core._db()  # type: ignore[attr-defined]


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _ensure_writable() -> None:
    if _is_read_only():
        raise PermissionError("read_only")


def _clean_text(value: str | None, max_len: int) -> str:
    text = (value or "").replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _policy_allows_calendar(policy_row: dict[str, Any]) -> bool:
    return bool(int(policy_row.get("allow_calendar", 0))) and bool(
        int(policy_row.get("allow_customer_pii", 0))
    )


def _insert_ingest_log(
    con: sqlite3.Connection,
    *,
    tenant_id: str,
    source_id: str,
    status: str,
    reason_code: str,
) -> None:
    con.execute(
        """
        INSERT INTO knowledge_ics_ingest_log(
          id, tenant_id, ics_source_id, status, reason_code, created_at
        ) VALUES (?,?,?,?,?,?)
        """,
        (_new_id(), tenant_id, source_id, status, reason_code, _now_iso()),
    )


def _upsert_fts_chunk(
    con: sqlite3.Connection, row_id: int, title: str, body: str, tags: str
) -> None:
    try:
        con.execute(
            "INSERT INTO knowledge_fts(rowid, title, body, tags) VALUES (?,?,?,?)",
            (row_id, title, body, tags),
        )
    except Exception:
        con.execute(
            "INSERT OR REPLACE INTO knowledge_fts_fallback(rowid, title, body, tags) VALUES (?,?,?,?)",
            (row_id, title, body, tags),
        )


def _decode_and_unfold(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace").replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    unfolded: list[str] = []
    for line in lines:
        if (line.startswith(" ") or line.startswith("\t")) and unfolded:
            unfolded[-1] = f"{unfolded[-1]} {line[1:]}"
        else:
            unfolded.append(line)
    out: list[str] = []
    for line in unfolded:
        if len(line) > MAX_LINE_LEN:
            out.append(line[:MAX_LINE_LEN])
        else:
            out.append(line)
    return out


def _parse_prop(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    left, right = line.split(":", 1)
    key = left.split(";", 1)[0].strip().upper()
    if not key:
        return None
    return key, right.strip()


def _parse_ics_dt(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if DATE_ONLY_RE.match(raw):
            dt = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=UTC)
            return dt.isoformat(timespec="seconds")
        if DATE_TIME_Z_RE.match(raw):
            dt = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            return dt.isoformat(timespec="seconds")
        if DATE_TIME_RE.match(raw):
            dt = datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
            return dt.isoformat(timespec="seconds")
    except Exception:
        return None
    return None


def _parse_events(lines: list[str]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    in_event = False
    current: dict[str, str] = {}
    for line in lines:
        tag = line.strip().upper()
        if tag == "BEGIN:VEVENT":
            in_event = True
            current = {}
            continue
        if tag == "END:VEVENT":
            if in_event:
                events.append(current)
                if len(events) >= MAX_EVENTS_PARSED:
                    break
            in_event = False
            current = {}
            continue
        if not in_event:
            continue

        parsed = _parse_prop(line)
        if not parsed:
            continue
        key, value = parsed
        if key in IGNORE_KEYS or key not in ALLOWED_KEYS:
            continue
        if key in current:
            continue
        if key in {"SUMMARY", "LOCATION"}:
            current[key] = _clean_text(value, MAX_FIELD_LEN)
        else:
            parsed_dt = _parse_ics_dt(value)
            if parsed_dt:
                current[key] = parsed_dt
    return events


def _event_body(event: dict[str, str]) -> str:
    parts: list[str] = []
    if event.get("DTSTART"):
        parts.append(f"start {event['DTSTART']}")
    if event.get("DTEND"):
        parts.append(f"end {event['DTEND']}")
    if event.get("SUMMARY"):
        parts.append(f"summary {event['SUMMARY']}")
    if event.get("LOCATION"):
        parts.append(f"location {event['LOCATION']}")
    return _clean_text(" | ".join(parts), MAX_FIELD_LEN * 4)


def knowledge_ics_ingest(
    tenant_id: str,
    actor_user_id: str | None,
    ics_bytes: bytes,
    filename_hint: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_calendar(policy_row):
        raise ValueError("policy_blocked")

    if not ics_bytes:
        raise ValueError("empty_file")

    max_bytes = MAX_ICS_BYTES
    if has_app_context():
        try:
            max_bytes = int(
                current_app.config.get("KNOWLEDGE_ICS_MAX_BYTES", MAX_ICS_BYTES)
            )
        except Exception:
            max_bytes = MAX_ICS_BYTES
    if len(ics_bytes) > max_bytes:
        raise ValueError("payload_too_large")

    lines = _decode_and_unfold(ics_bytes)
    events = _parse_events(lines)
    content_sha = sha256(ics_bytes).hexdigest()
    filename = _clean_text(filename_hint or "upload.ics", 180)
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            "SELECT id FROM knowledge_ics_sources WHERE tenant_id=? AND content_sha256=? LIMIT 1",
            (tenant, content_sha),
        ).fetchone()
        created_new = row is None
        if created_new:
            source_id = _new_id()
            con.execute(
                """
                INSERT INTO knowledge_ics_sources(
                  id, tenant_id, content_sha256, filename, event_count, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    source_id,
                    tenant,
                    content_sha,
                    filename,
                    int(len(events)),
                    now,
                    now,
                ),
            )
        else:
            source_id = str(row["id"])
            con.execute(
                "UPDATE knowledge_ics_sources SET updated_at=? WHERE tenant_id=? AND id=?",
                (now, tenant, source_id),
            )

        chunks_created = 0
        if created_new:
            for idx, event in enumerate(events[:MAX_CHUNKS_WRITTEN]):
                body = _event_body(event)
                if not body:
                    continue
                title = _clean_text(
                    event.get("SUMMARY") or f"Calendar event {idx + 1}", MAX_FIELD_LEN
                )
                chunk_id = _new_id()
                source_ref = f"calendar:{source_id}"
                c_hash = sha256(body.encode("utf-8")).hexdigest()
                cur = con.execute(
                    """
                    INSERT OR IGNORE INTO knowledge_chunks(
                      chunk_id, tenant_id, owner_user_id, source_type, source_ref,
                      title, body, tags, content_hash, is_redacted, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        chunk_id,
                        tenant,
                        actor_user_id or None,
                        "calendar",
                        source_ref,
                        title,
                        body,
                        "calendar,ingested",
                        c_hash,
                        1,
                        now,
                        now,
                    ),
                )
                if int(cur.rowcount or 0) > 0:
                    chunks_created += 1
                    row2 = con.execute(
                        "SELECT id FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
                        (tenant, chunk_id),
                    ).fetchone()
                    if row2:
                        _upsert_fts_chunk(
                            con,
                            int(row2["id"]),
                            title,
                            body,
                            "calendar,ingested",
                        )

            if chunks_created == 0:
                _insert_ingest_log(
                    con,
                    tenant_id=tenant,
                    source_id=source_id,
                    status="rejected",
                    reason_code="no_supported_events",
                )
            else:
                _insert_ingest_log(
                    con,
                    tenant_id=tenant,
                    source_id=source_id,
                    status="ok",
                    reason_code="ingested",
                )
                event_append(
                    event_type="knowledge_ics_ingested",
                    entity_type="knowledge_ics",
                    entity_id=entity_id_int(source_id),
                    payload={
                        "schema_version": 1,
                        "source": "knowledge/ics_ingest",
                        "actor_user_id": actor_user_id,
                        "tenant_id": tenant,
                        "data": {
                            "source_id": source_id,
                            "content_sha256_prefix": content_sha[:12],
                            "events_parsed": int(len(events)),
                            "chunks_created": int(chunks_created),
                            "filename_present": bool(filename_hint),
                        },
                    },
                    con=con,
                )
        else:
            _insert_ingest_log(
                con,
                tenant_id=tenant,
                source_id=source_id,
                status="ok",
                reason_code="dedup",
            )

        return {
            "source_id": source_id,
            "tenant_id": tenant,
            "dedup": not created_new,
            "events_parsed": int(len(events)),
            "chunks_created": int(chunks_created),
            "filename": filename,
        }

    return _run_write_txn(_tx)


def knowledge_ics_sources_list(
    tenant_id: str, page: int = 1, page_size: int = 25
) -> tuple[list[dict[str, Any]], int]:
    tenant = _tenant(tenant_id)
    p = max(1, int(page))
    ps = max(1, min(int(page_size), 100))
    offset = (p - 1) * ps
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rows = con.execute(
                """
                SELECT id, content_sha256, filename, event_count, created_at, updated_at
                FROM knowledge_ics_sources
                WHERE tenant_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (tenant, ps, offset),
            ).fetchall()
            total_row = con.execute(
                "SELECT COUNT(*) AS n FROM knowledge_ics_sources WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
            total = int(total_row["n"] if total_row else 0)
            return [dict(r) for r in rows], total
        finally:
            con.close()
