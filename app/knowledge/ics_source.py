from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
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
MAX_OCR_TEXT_BYTES = 512 * 1024
MAX_OCR_DEADLINES_PARSED = 32
MAX_FEED_EVENTS = 1500
DEFAULT_FEED_PAST_DAYS = 45
DEFAULT_FEED_FUTURE_DAYS = 540

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

OCR_DMY_DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
OCR_YMD_DATE_RE = re.compile(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b")
OCR_TERM_DAYS_RE = re.compile(r"\b(\d{1,3})\s*(?:tage|tag|days?)\b", re.IGNORECASE)
OCR_DOC_REF_RE = re.compile(
    r"\b(?:rechnung|invoice|angebot|offer|lieferschein|delivery(?:\s|-)?note|auftrag|order)\D{0,14}([A-Z0-9][A-Z0-9/_-]{2,})\b",
    re.IGNORECASE,
)
OCR_SKONTO_HINTS = (
    "skonto",
    "discount",
)
OCR_PAYMENT_HINTS = (
    "zahlbar",
    "fallig",
    "zahlungsziel",
    "zahlung",
    "netto",
    "due date",
    "payment due",
)
OCR_DELIVERY_HINTS = (
    "liefertermin",
    "lieferdatum",
    "lieferung",
    "bereitstellung",
    "delivery date",
    "delivery by",
)
OCR_REFERENCE_HINTS = (
    "rechnungsdatum",
    "invoice date",
    "belegdatum",
    "angebotsdatum",
    "angebot vom",
    "datum",
)
OCR_DEADLINE_SCHEMA = "ocr_deadline.v1"


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


def _normalize_ocr_text(text: str | None, max_len: int = MAX_OCR_TEXT_BYTES) -> str:
    value = (text or "").replace("\x00", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", value)
    value = value.strip()
    if len(value) > max_len:
        value = value[:max_len]
    return value


def _policy_allows_calendar(policy_row: dict[str, Any]) -> bool:
    return bool(int(policy_row.get("allow_calendar", 0))) and bool(
        int(policy_row.get("allow_customer_pii", 0))
    )


def _policy_allows_ocr_calendar(policy_row: dict[str, Any]) -> bool:
    return _policy_allows_calendar(policy_row) and bool(int(policy_row.get("allow_ocr", 0)))


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


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except Exception:
        return None


def _parse_ocr_date_token(raw: str) -> date | None:
    token = (raw or "").strip()
    if not token:
        return None
    m_ymd = OCR_YMD_DATE_RE.fullmatch(token)
    if m_ymd:
        return _safe_date(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
    m_dmy = OCR_DMY_DATE_RE.fullmatch(token)
    if m_dmy:
        day = int(m_dmy.group(1))
        month = int(m_dmy.group(2))
        year = int(m_dmy.group(3))
        if year < 100:
            year = 2000 + year
        return _safe_date(year, month, day)
    return None


def _extract_doc_ref(ocr_text: str, filename_hint: str | None) -> str:
    m = OCR_DOC_REF_RE.search(ocr_text)
    if m:
        return _clean_text(m.group(1), 64)
    if filename_hint:
        return _clean_text(Path(filename_hint).stem, 64)
    return "Dokument"


def _line_for_index(text: str, idx: int) -> str:
    start = text.rfind("\n", 0, max(0, idx))
    end = text.find("\n", idx)
    if start < 0:
        start = 0
    else:
        start += 1
    if end < 0:
        end = len(text)
    return _clean_text(text[start:end], 500)


def _context_window(text: str, idx: int, radius: int = 44) -> str:
    start = max(0, idx - radius)
    end = min(len(text), idx + radius)
    return _clean_text(text[start:end], 256).lower()


def _extract_date_candidates(ocr_text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []

    def _is_overlapping(start: int, end: int) -> bool:
        for o_start, o_end in occupied:
            if start < o_end and end > o_start:
                return True
        return False

    for m in OCR_YMD_DATE_RE.finditer(ocr_text):
        parsed = _parse_ocr_date_token(m.group(0))
        if not parsed:
            continue
        occupied.append((m.start(), m.end()))
        out.append({"date": parsed, "idx": m.start(), "raw": m.group(0)})

    for m in OCR_DMY_DATE_RE.finditer(ocr_text):
        if _is_overlapping(m.start(), m.end()):
            continue
        parsed = _parse_ocr_date_token(m.group(0))
        if not parsed:
            continue
        occupied.append((m.start(), m.end()))
        out.append({"date": parsed, "idx": m.start(), "raw": m.group(0)})

    out.sort(key=lambda item: int(item["idx"]))
    return out


def _extract_reference_date(ocr_text: str, cands: list[dict[str, Any]]) -> date | None:
    best: date | None = None
    best_score = -1.0
    for cand in cands:
        d = cand["date"]
        if not isinstance(d, date):
            continue
        idx = int(cand["idx"])
        line = _line_for_index(ocr_text, idx).lower()
        score = 0.2
        if any(h in line for h in OCR_REFERENCE_HINTS):
            score += 1.5
        if any(h in line for h in OCR_PAYMENT_HINTS + OCR_SKONTO_HINTS + OCR_DELIVERY_HINTS):
            score -= 1.3
        if score > best_score:
            best = d
            best_score = score
    if best is not None:
        return best
    if cands:
        first = cands[0].get("date")
        if isinstance(first, date):
            return first
    return None


def _deadline_kind_from_context(ctx: str) -> str | None:
    if any(h in ctx for h in OCR_SKONTO_HINTS):
        return "discount_due"
    if any(h in ctx for h in OCR_PAYMENT_HINTS):
        return "payment_due"
    if any(h in ctx for h in OCR_DELIVERY_HINTS):
        return "delivery_due"
    return None


def _deadline_summary(kind: str, doc_ref: str) -> str:
    if kind == "discount_due":
        return _clean_text(f"Skonto deadline ({doc_ref})", MAX_FIELD_LEN)
    if kind == "payment_due":
        return _clean_text(f"Payment deadline ({doc_ref})", MAX_FIELD_LEN)
    if kind == "delivery_due":
        return _clean_text(f"Delivery date ({doc_ref})", MAX_FIELD_LEN)
    return _clean_text(f"Deadline ({doc_ref})", MAX_FIELD_LEN)


def _deadline_tags(kind: str) -> str:
    if kind == "discount_due":
        return "calendar,ocr,deadline,discount"
    if kind == "payment_due":
        return "calendar,ocr,deadline,payment"
    if kind == "delivery_due":
        return "calendar,ocr,deadline,delivery"
    return "calendar,ocr,deadline"


def _build_deadline_event(
    *,
    kind: str,
    due_date: date,
    excerpt: str,
    filename_hint: str | None,
    doc_ref: str,
) -> dict[str, str]:
    return {
        "schema": OCR_DEADLINE_SCHEMA,
        "kind": kind,
        "due_date": due_date.isoformat(),
        "summary": _deadline_summary(kind, doc_ref),
        "source_filename": _clean_text(filename_hint or "", 180),
        "source_doc_ref": _clean_text(doc_ref, 64),
        "excerpt": _clean_text(excerpt, MAX_FIELD_LEN * 4),
    }


def _extract_deadline_events_from_ocr_text(
    ocr_text: str,
    *,
    filename_hint: str | None = None,
    max_events: int = MAX_OCR_DEADLINES_PARSED,
) -> list[dict[str, str]]:
    normalized = _normalize_ocr_text(ocr_text)
    if not normalized:
        return []

    doc_ref = _extract_doc_ref(normalized, filename_hint)
    candidates = _extract_date_candidates(normalized)
    reference_date = _extract_reference_date(normalized, candidates)

    events: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for cand in candidates:
        due = cand.get("date")
        if not isinstance(due, date):
            continue
        idx = int(cand["idx"])
        line = _line_for_index(normalized, idx)
        line_l = line.lower()
        kind = _deadline_kind_from_context(line_l)
        if not kind:
            near_ctx = _context_window(normalized, idx, radius=28)
            kind = _deadline_kind_from_context(near_ctx)
        if not kind:
            continue
        if any(h in line_l for h in OCR_REFERENCE_HINTS):
            if not any(
                h in line_l for h in (OCR_PAYMENT_HINTS + OCR_SKONTO_HINTS + OCR_DELIVERY_HINTS)
            ):
                continue
        key = (kind, due.isoformat())
        if key in seen:
            continue
        seen.add(key)
        events.append(
            _build_deadline_event(
                kind=kind,
                due_date=due,
                excerpt=line,
                filename_hint=filename_hint,
                doc_ref=doc_ref,
            )
        )
        if len(events) >= max_events:
            break

    if reference_date is not None and len(events) < max_events:
        for raw_line in normalized.splitlines():
            line = _clean_text(raw_line, 500)
            if not line:
                continue
            line_l = line.lower()
            term_m = OCR_TERM_DAYS_RE.search(line_l)
            if not term_m:
                continue
            kind = _deadline_kind_from_context(line_l)
            if not kind:
                continue
            days = int(term_m.group(1))
            if days <= 0 or days > 365:
                continue
            due = reference_date + timedelta(days=days)
            key = (kind, due.isoformat())
            if key in seen:
                continue
            seen.add(key)
            events.append(
                _build_deadline_event(
                    kind=kind,
                    due_date=due,
                    excerpt=line,
                    filename_hint=filename_hint,
                    doc_ref=doc_ref,
                )
            )
            if len(events) >= max_events:
                break

    events.sort(key=lambda ev: (ev.get("due_date", ""), ev.get("kind", ""), ev.get("summary", "")))
    return events[:max_events]


def _serialize_deadline_event(event: dict[str, str]) -> str:
    payload = {
        "schema": OCR_DEADLINE_SCHEMA,
        "kind": _clean_text(event.get("kind"), 40),
        "due_date": _clean_text(event.get("due_date"), 20),
        "summary": _clean_text(event.get("summary"), MAX_FIELD_LEN),
        "source_filename": _clean_text(event.get("source_filename"), 180),
        "source_doc_ref": _clean_text(event.get("source_doc_ref"), 64),
        "excerpt": _clean_text(event.get("excerpt"), MAX_FIELD_LEN * 4),
    }
    return _clean_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        MAX_FIELD_LEN * 8,
    )


def _deserialize_deadline_event(body: str | None) -> dict[str, str] | None:
    raw = (body or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    if str(obj.get("schema", "")) != OCR_DEADLINE_SCHEMA:
        return None
    due_str = str(obj.get("due_date", ""))
    due = _parse_ocr_date_token(due_str)
    if due is None:
        try:
            due = date.fromisoformat(due_str)
        except Exception:
            return None
    kind = _clean_text(str(obj.get("kind", "")), 40)
    if kind not in {"discount_due", "payment_due", "delivery_due"}:
        return None
    return {
        "schema": OCR_DEADLINE_SCHEMA,
        "kind": kind,
        "due_date": due.isoformat(),
        "summary": _clean_text(str(obj.get("summary", "")), MAX_FIELD_LEN),
        "source_filename": _clean_text(str(obj.get("source_filename", "")), 180),
        "source_doc_ref": _clean_text(str(obj.get("source_doc_ref", "")), 64),
        "excerpt": _clean_text(str(obj.get("excerpt", "")), MAX_FIELD_LEN * 4),
    }


def _ics_escape(value: str | None) -> str:
    out = (value or "").replace("\\", "\\\\")
    out = out.replace(";", r"\;").replace(",", r"\,")
    out = out.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\n")
    return out


def _ics_fold(line: str, width: int = 72) -> list[str]:
    if len(line) <= width:
        return [line]
    out = [line[:width]]
    rest = line[width:]
    while rest:
        out.append(f" {rest[: width - 1]}")
        rest = rest[width - 1 :]
    return out


def _feed_past_days() -> int:
    value = DEFAULT_FEED_PAST_DAYS
    if has_app_context():
        try:
            value = int(current_app.config.get("KNOWLEDGE_ICS_FEED_PAST_DAYS", value))
        except Exception:
            value = DEFAULT_FEED_PAST_DAYS
    return max(0, min(value, 365))


def _feed_future_days() -> int:
    value = DEFAULT_FEED_FUTURE_DAYS
    if has_app_context():
        try:
            value = int(current_app.config.get("KNOWLEDGE_ICS_FEED_FUTURE_DAYS", value))
        except Exception:
            value = DEFAULT_FEED_FUTURE_DAYS
    return max(1, min(value, 730))


def _feed_dir() -> Path:
    if has_app_context():
        configured = str(current_app.config.get("KNOWLEDGE_ICS_FEED_DIR", "") or "").strip()
        if configured:
            return Path(configured).expanduser()
        return Path(current_app.instance_path) / "calendar_feeds"

    env = (
        os.environ.get("KUKANILEA_ICS_FEED_DIR")
        or os.environ.get("TOPHANDWERK_ICS_FEED_DIR")
        or ""
    ).strip()
    if env:
        return Path(env).expanduser()
    return Path.cwd() / "instance" / "calendar_feeds"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip().lower()).strip("-._")
    return slug or "default"


def _feed_path(tenant_id: str) -> Path:
    return _feed_dir() / f"{_slugify(tenant_id)}-deadlines.ics"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def _read_ocr_deadline_events(tenant_id: str) -> list[dict[str, str]]:
    limit = MAX_FEED_EVENTS
    if has_app_context():
        try:
            limit = int(current_app.config.get("KNOWLEDGE_ICS_FEED_MAX_EVENTS", MAX_FEED_EVENTS))
        except Exception:
            limit = MAX_FEED_EVENTS
    limit = max(1, min(limit, 5000))

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            try:
                rows = con.execute(
                    """
                    SELECT chunk_id, body, source_ref
                    FROM knowledge_chunks
                    WHERE tenant_id=? AND source_type='calendar' AND source_ref LIKE 'calendar_ocr:%'
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (tenant_id, limit),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower():
                    rows = []
                else:
                    raise
        finally:
            con.close()

    today = datetime.now(UTC).date()
    min_due = today - timedelta(days=_feed_past_days())
    max_due = today + timedelta(days=_feed_future_days())

    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for row in rows:
        event = _deserialize_deadline_event(row["body"])
        if not event:
            continue
        due = _parse_ocr_date_token(event.get("due_date"))
        if due is None:
            try:
                due = date.fromisoformat(event["due_date"])
            except Exception:
                continue
        if due < min_due or due > max_due:
            continue
        key = (
            event.get("kind", ""),
            due.isoformat(),
            event.get("source_doc_ref", "") or event.get("summary", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(event)

    out.sort(key=lambda ev: (ev.get("due_date", ""), ev.get("kind", ""), ev.get("summary", "")))
    return out


def _render_deadline_ics(tenant_id: str, events: list[dict[str, str]]) -> bytes:
    now = datetime.now(UTC)
    dtstamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KUKANILEA//Strategic Scheduling//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(f'KUKANILEA Deadlines ({tenant_id})')}",
        "X-WR-TIMEZONE:UTC",
    ]

    for event in events:
        due = _parse_ocr_date_token(event.get("due_date"))
        if due is None:
            try:
                due = date.fromisoformat(event.get("due_date", ""))
            except Exception:
                continue
        due_next = due + timedelta(days=1)
        uid_seed = "|".join(
            [
                tenant_id,
                event.get("kind", ""),
                due.isoformat(),
                event.get("source_doc_ref", ""),
                event.get("summary", ""),
            ]
        )
        uid = f"{sha256(uid_seed.encode('utf-8')).hexdigest()[:30]}@kukanilea.local"

        kind = event.get("kind", "")
        categories = "KUKANILEA,DEADLINE"
        if kind == "discount_due":
            categories = "KUKANILEA,DEADLINE,SKONTO"
        elif kind == "payment_due":
            categories = "KUKANILEA,DEADLINE,PAYMENT"
        elif kind == "delivery_due":
            categories = "KUKANILEA,DEADLINE,DELIVERY"

        description = event.get("excerpt", "")
        if event.get("source_filename"):
            description = f"{description} source={event['source_filename']}".strip()

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{due_next.strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(event.get('summary', 'Deadline'))}",
                f"DESCRIPTION:{_ics_escape(description)}",
                f"CATEGORIES:{categories}",
                "STATUS:CONFIRMED",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_ics_escape(event.get('summary', 'Deadline reminder'))}",
                "TRIGGER:-P1D",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    folded: list[str] = []
    for line in lines:
        folded.extend(_ics_fold(line))
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")


def knowledge_ics_extract_deadlines_from_ocr(
    ocr_text: str, filename_hint: str | None = None
) -> list[dict[str, str]]:
    return _extract_deadline_events_from_ocr_text(
        ocr_text, filename_hint=filename_hint, max_events=MAX_OCR_DEADLINES_PARSED
    )


def knowledge_ics_ingest_ocr_text(
    tenant_id: str,
    actor_user_id: str | None,
    ocr_text: str,
    filename_hint: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_ocr_calendar(policy_row):
        raise ValueError("policy_blocked")

    normalized_text = _normalize_ocr_text(ocr_text)
    if not normalized_text:
        raise ValueError("empty_text")

    events = _extract_deadline_events_from_ocr_text(
        normalized_text,
        filename_hint=filename_hint,
        max_events=MAX_OCR_DEADLINES_PARSED,
    )

    content_sha = sha256(normalized_text.encode("utf-8")).hexdigest()
    filename = _clean_text(filename_hint or "ocr_text.txt", 180)
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
                """
                UPDATE knowledge_ics_sources
                SET updated_at=?, event_count=?, filename=?
                WHERE tenant_id=? AND id=?
                """,
                (now, int(len(events)), filename, tenant, source_id),
            )

        chunks_created = 0
        if created_new:
            for event in events[:MAX_CHUNKS_WRITTEN]:
                body = _serialize_deadline_event(event)
                if not body:
                    continue

                title = _clean_text(event.get("summary"), MAX_FIELD_LEN)
                tags = _deadline_tags(str(event.get("kind", "")))
                chunk_id = _new_id()
                source_ref = f"calendar_ocr:{source_id}"
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
                        tags,
                        c_hash,
                        1,
                        now,
                        now,
                    ),
                )
                if int(cur.rowcount or 0) <= 0:
                    continue

                chunks_created += 1
                row2 = con.execute(
                    "SELECT id FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
                    (tenant, chunk_id),
                ).fetchone()
                if row2:
                    _upsert_fts_chunk(con, int(row2["id"]), title, body, tags)

            if chunks_created == 0:
                _insert_ingest_log(
                    con,
                    tenant_id=tenant,
                    source_id=source_id,
                    status="rejected",
                    reason_code="no_deadlines",
                )
            else:
                _insert_ingest_log(
                    con,
                    tenant_id=tenant,
                    source_id=source_id,
                    status="ok",
                    reason_code="ocr_deadlines_ingested",
                )
                event_append(
                    event_type="knowledge_ics_ocr_ingested",
                    entity_type="knowledge_ics",
                    entity_id=entity_id_int(source_id),
                    payload={
                        "schema_version": 1,
                        "source": "knowledge/ics_ocr_ingest",
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

    result = _run_write_txn(_tx)
    try:
        feed_info = knowledge_ics_build_local_feed(tenant)
        result["feed_path"] = str(feed_info.get("feed_path", ""))
        result["feed_filename"] = str(feed_info.get("feed_filename", ""))
        result["feed_event_count"] = int(feed_info.get("event_count", 0))
    except Exception:
        result["feed_path"] = ""
        result["feed_filename"] = ""
        result["feed_event_count"] = 0
    return result


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

    result = _run_write_txn(_tx)
    try:
        feed_info = knowledge_ics_build_local_feed(tenant)
        result["feed_path"] = str(feed_info.get("feed_path", ""))
        result["feed_filename"] = str(feed_info.get("feed_filename", ""))
        result["feed_event_count"] = int(feed_info.get("event_count", 0))
    except Exception:
        result["feed_path"] = ""
        result["feed_filename"] = ""
        result["feed_event_count"] = 0
    return result


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

MANUAL_EVENT_SCHEMA = "calendar_manual_event.v1"
MANUAL_SOURCE_PREFIX = "calendar_manual:"


def _parse_iso_datetime(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _parse_iso_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except Exception:
        return None


def _normalize_kind(kind: str | None) -> str:
    value = _clean_text(kind or "general", 40).lower()
    return value or "general"


def _safe_recurrence(recurrence: dict[str, Any] | None) -> dict[str, Any]:
    if not recurrence:
        return {}
    freq = _clean_text(str(recurrence.get("freq", "")).lower(), 16)
    if freq not in {"daily", "weekly", "monthly"}:
        return {}
    interval = int(recurrence.get("interval", 1) or 1)
    interval = max(1, min(interval, 31))
    count = int(recurrence.get("count", 0) or 0)
    count = max(0, min(count, 366))
    until = _parse_iso_date(str(recurrence.get("until", "")) if recurrence.get("until") else "")
    out: dict[str, Any] = {"freq": freq, "interval": interval}
    if count > 0:
        out["count"] = count
    if until is not None:
        out["until"] = until.isoformat()
    return out


def _manual_event_payload(
    *,
    event_id: str,
    title: str,
    start_at: str,
    end_at: str,
    all_day: bool,
    kind: str,
    location: str,
    notes: str,
    reminder_minutes: int,
    recurrence: dict[str, Any] | None,
    status: str,
    owner_user_id: str | None,
) -> dict[str, Any]:
    return {
        "schema": MANUAL_EVENT_SCHEMA,
        "event_id": event_id,
        "title": _clean_text(title, MAX_FIELD_LEN),
        "start_at": start_at,
        "end_at": end_at,
        "all_day": 1 if all_day else 0,
        "kind": _normalize_kind(kind),
        "location": _clean_text(location, MAX_FIELD_LEN),
        "notes": _clean_text(notes, MAX_FIELD_LEN * 4),
        "reminder_minutes": max(0, min(int(reminder_minutes or 0), 10080)),
        "recurrence": _safe_recurrence(recurrence),
        "status": _clean_text(status, 16) or "active",
        "owner_user_id": _clean_text(owner_user_id or "", 120),
    }


def _serialize_manual_event(payload: dict[str, Any]) -> str:
    return _clean_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        MAX_FIELD_LEN * 10,
    )


def _deserialize_manual_event(body: str | None) -> dict[str, Any] | None:
    raw = (body or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    if str(obj.get("schema", "")) != MANUAL_EVENT_SCHEMA:
        return None

    title = _clean_text(str(obj.get("title", "")), MAX_FIELD_LEN)
    if not title:
        return None

    all_day = bool(int(obj.get("all_day", 0) or 0))
    start_at = _clean_text(str(obj.get("start_at", "")), 64)
    end_at = _clean_text(str(obj.get("end_at", "")), 64)

    if all_day:
        s_date = _parse_iso_date(start_at)
        e_date = _parse_iso_date(end_at)
        if not s_date or not e_date or e_date < s_date:
            return None
    else:
        s_dt = _parse_iso_datetime(start_at)
        e_dt = _parse_iso_datetime(end_at)
        if not s_dt or not e_dt or e_dt < s_dt:
            return None

    recurrence = _safe_recurrence(obj.get("recurrence") if isinstance(obj.get("recurrence"), dict) else {})
    return {
        "schema": MANUAL_EVENT_SCHEMA,
        "event_id": _clean_text(str(obj.get("event_id", "")), 64),
        "title": title,
        "start_at": start_at,
        "end_at": end_at,
        "all_day": 1 if all_day else 0,
        "kind": _normalize_kind(str(obj.get("kind", "general"))),
        "location": _clean_text(str(obj.get("location", "")), MAX_FIELD_LEN),
        "notes": _clean_text(str(obj.get("notes", "")), MAX_FIELD_LEN * 4),
        "reminder_minutes": max(0, min(int(obj.get("reminder_minutes", 0) or 0), 10080)),
        "recurrence": recurrence,
        "status": _clean_text(str(obj.get("status", "active")), 16) or "active",
        "owner_user_id": _clean_text(str(obj.get("owner_user_id", "")), 120),
    }


def _manual_source_ref(event_id: str) -> str:
    return f"{MANUAL_SOURCE_PREFIX}{_clean_text(event_id, 64)}"


def _month_add(dt: datetime, months: int) -> datetime:
    year = dt.year + ((dt.month - 1 + months) // 12)
    month = ((dt.month - 1 + months) % 12) + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)


def _expand_manual_event_occurrences(
    event: dict[str, Any],
    *,
    range_start: datetime,
    range_end: datetime,
    max_instances: int = 366,
) -> list[dict[str, Any]]:
    if event.get("status") != "active":
        return []

    all_day = bool(int(event.get("all_day", 0) or 0))
    rec = event.get("recurrence") if isinstance(event.get("recurrence"), dict) else {}
    freq = str(rec.get("freq", ""))
    interval = max(1, min(int(rec.get("interval", 1) or 1), 31))
    count_limit = max(0, min(int(rec.get("count", 0) or 0), max_instances))
    until_date = _parse_iso_date(str(rec.get("until", "")) if rec.get("until") else "")

    if all_day:
        s_date = _parse_iso_date(str(event.get("start_at", "")))
        e_date = _parse_iso_date(str(event.get("end_at", "")))
        if not s_date or not e_date:
            return []
        start = datetime(s_date.year, s_date.month, s_date.day, tzinfo=UTC)
        end = datetime(e_date.year, e_date.month, e_date.day, tzinfo=UTC)
    else:
        start = _parse_iso_datetime(str(event.get("start_at", "")))
        end = _parse_iso_datetime(str(event.get("end_at", "")))
        if not start or not end:
            return []

    out: list[dict[str, Any]] = []
    current_start = start
    current_end = end
    n = 0

    while n < max_instances:
        if until_date is not None and current_start.date() > until_date:
            break
        if current_end >= range_start and current_start <= range_end:
            out.append(
                {
                    **event,
                    "occurrence_start": current_start.isoformat(timespec="seconds"),
                    "occurrence_end": current_end.isoformat(timespec="seconds"),
                }
            )
        n += 1
        if count_limit > 0 and n >= count_limit:
            break
        if not freq:
            break
        if freq == "daily":
            current_start = current_start + timedelta(days=interval)
            current_end = current_end + timedelta(days=interval)
        elif freq == "weekly":
            current_start = current_start + timedelta(days=7 * interval)
            current_end = current_end + timedelta(days=7 * interval)
        elif freq == "monthly":
            current_start = _month_add(current_start, interval)
            current_end = _month_add(current_end, interval)
        else:
            break
        if current_start > range_end and not freq:
            break

    return out


def _read_manual_events(tenant_id: str, owner_user_id: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [tenant_id]
    where = "WHERE tenant_id=? AND source_type='calendar' AND source_ref LIKE ?"
    params.append(f"{MANUAL_SOURCE_PREFIX}%")
    if owner_user_id:
        where += " AND owner_user_id=?"
        params.append(owner_user_id)

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            try:
                rows = con.execute(
                    f"""
                    SELECT chunk_id, owner_user_id, source_ref, title, body, tags, created_at, updated_at
                    FROM knowledge_chunks
                    {where}
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                    """,
                    tuple(params),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                # Test/bootstrap databases may not have the optional knowledge_chunks table yet.
                if "no such table" in str(exc).lower():
                    rows = []
                else:
                    raise
        finally:
            con.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        event = _deserialize_manual_event(row["body"])
        if not event:
            continue
        event["chunk_id"] = str(row["chunk_id"])
        event["owner_user_id"] = _clean_text(str(row["owner_user_id"] or event.get("owner_user_id", "")), 120)
        event["source_ref"] = str(row["source_ref"])
        out.append(event)
    return out


def knowledge_calendar_event_create(
    tenant_id: str,
    actor_user_id: str | None,
    *,
    title: str,
    start_at: str,
    end_at: str | None = None,
    all_day: bool = False,
    kind: str = "general",
    location: str | None = None,
    notes: str | None = None,
    reminder_minutes: int = 0,
    recurrence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_calendar(policy_row):
        raise ValueError("policy_blocked")

    t = _clean_text(title, MAX_FIELD_LEN)
    if not t:
        raise ValueError("validation_error")

    if all_day:
        s_date = _parse_iso_date(start_at)
        e_date = _parse_iso_date(end_at or start_at)
        if not s_date or not e_date or e_date < s_date:
            raise ValueError("validation_error")
        start_norm = s_date.isoformat()
        end_norm = e_date.isoformat()
    else:
        s_dt = _parse_iso_datetime(start_at)
        e_dt = _parse_iso_datetime(end_at or start_at)
        if not s_dt or not e_dt or e_dt < s_dt:
            raise ValueError("validation_error")
        start_norm = s_dt.isoformat(timespec="seconds")
        end_norm = e_dt.isoformat(timespec="seconds")

    event_id = _new_id()
    payload = _manual_event_payload(
        event_id=event_id,
        title=t,
        start_at=start_norm,
        end_at=end_norm,
        all_day=all_day,
        kind=kind,
        location=location or "",
        notes=notes or "",
        reminder_minutes=reminder_minutes,
        recurrence=recurrence,
        status="active",
        owner_user_id=actor_user_id,
    )

    now = _now_iso()
    source_ref = _manual_source_ref(event_id)
    body = _serialize_manual_event(payload)
    c_hash = sha256(body.encode("utf-8")).hexdigest()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        chunk_id = _new_id()
        con.execute(
            """
            INSERT INTO knowledge_chunks(
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
                t,
                body,
                f"calendar,manual,{_normalize_kind(kind)}",
                c_hash,
                0,
                now,
                now,
            ),
        )
        row = con.execute(
            "SELECT id FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
            (tenant, chunk_id),
        ).fetchone()
        if row:
            _upsert_fts_chunk(con, int(row["id"]), t, body, f"calendar,manual,{_normalize_kind(kind)}")

        event_append(
            event_type="calendar_manual_event_created",
            entity_type="calendar_event",
            entity_id=entity_id_int(event_id),
            payload={
                "schema_version": 1,
                "source": "calendar/manual_create",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "event_id": event_id,
                    "kind": _normalize_kind(kind),
                    "all_day": int(bool(all_day)),
                    "has_recurrence": int(bool(payload.get("recurrence"))),
                },
            },
            con=con,
        )

        return {
            "event_id": event_id,
            "chunk_id": chunk_id,
            "tenant_id": tenant,
            "title": t,
            "source_ref": source_ref,
        }

    result = _run_write_txn(_tx)
    try:
        feed = knowledge_ics_build_local_feed(tenant)
        result["feed_path"] = str(feed.get("feed_path", ""))
    except Exception:
        result["feed_path"] = ""
    return result


def knowledge_calendar_event_update(
    tenant_id: str,
    actor_user_id: str | None,
    *,
    event_id: str,
    title: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    all_day: bool | None = None,
    kind: str | None = None,
    location: str | None = None,
    notes: str | None = None,
    reminder_minutes: int | None = None,
    recurrence: dict[str, Any] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_calendar(policy_row):
        raise ValueError("policy_blocked")
    source_ref = _manual_source_ref(event_id)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT chunk_id, body
            FROM knowledge_chunks
            WHERE tenant_id=? AND source_type='calendar' AND source_ref=?
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            (tenant, source_ref),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        existing = _deserialize_manual_event(row["body"])
        if not existing:
            raise ValueError("not_found")

        eff_all_day = bool(int(existing.get("all_day", 0) or 0)) if all_day is None else bool(all_day)
        new_start = start_at or str(existing.get("start_at", ""))
        new_end = end_at or str(existing.get("end_at", ""))

        if eff_all_day:
            s_date = _parse_iso_date(new_start)
            e_date = _parse_iso_date(new_end)
            if not s_date or not e_date or e_date < s_date:
                raise ValueError("validation_error")
            start_norm = s_date.isoformat()
            end_norm = e_date.isoformat()
        else:
            s_dt = _parse_iso_datetime(new_start)
            e_dt = _parse_iso_datetime(new_end)
            if not s_dt or not e_dt or e_dt < s_dt:
                raise ValueError("validation_error")
            start_norm = s_dt.isoformat(timespec="seconds")
            end_norm = e_dt.isoformat(timespec="seconds")

        payload = _manual_event_payload(
            event_id=_clean_text(event_id, 64),
            title=title or str(existing.get("title", "")),
            start_at=start_norm,
            end_at=end_norm,
            all_day=eff_all_day,
            kind=kind or str(existing.get("kind", "general")),
            location=location if location is not None else str(existing.get("location", "")),
            notes=notes if notes is not None else str(existing.get("notes", "")),
            reminder_minutes=existing.get("reminder_minutes", 0) if reminder_minutes is None else reminder_minutes,
            recurrence=existing.get("recurrence") if recurrence is None else recurrence,
            status=status or str(existing.get("status", "active")),
            owner_user_id=str(existing.get("owner_user_id", actor_user_id or "")),
        )

        body = _serialize_manual_event(payload)
        c_hash = sha256(body.encode("utf-8")).hexdigest()
        now = _now_iso()

        con.execute(
            """
            UPDATE knowledge_chunks
            SET title=?, body=?, tags=?, content_hash=?, updated_at=?
            WHERE tenant_id=? AND source_type='calendar' AND source_ref=?
            """,
            (
                payload["title"],
                body,
                f"calendar,manual,{payload['kind']}",
                c_hash,
                now,
                tenant,
                source_ref,
            ),
        )

        event_append(
            event_type="calendar_manual_event_updated",
            entity_type="calendar_event",
            entity_id=entity_id_int(event_id),
            payload={
                "schema_version": 1,
                "source": "calendar/manual_update",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "event_id": event_id,
                },
            },
            con=con,
        )

        return {
            "event_id": event_id,
            "tenant_id": tenant,
            "title": payload["title"],
        }

    result = _run_write_txn(_tx)
    try:
        feed = knowledge_ics_build_local_feed(tenant)
        result["feed_path"] = str(feed.get("feed_path", ""))
    except Exception:
        result["feed_path"] = ""
    return result


def knowledge_calendar_event_delete(
    tenant_id: str,
    actor_user_id: str | None,
    *,
    event_id: str,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_calendar(policy_row):
        raise ValueError("policy_blocked")
    source_ref = _manual_source_ref(event_id)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            "SELECT COUNT(*) AS n FROM knowledge_chunks WHERE tenant_id=? AND source_type='calendar' AND source_ref=?",
            (tenant, source_ref),
        ).fetchone()
        if not row or int(row["n"] or 0) <= 0:
            raise ValueError("not_found")

        con.execute(
            "DELETE FROM knowledge_chunks WHERE tenant_id=? AND source_type='calendar' AND source_ref=?",
            (tenant, source_ref),
        )

        event_append(
            event_type="calendar_manual_event_deleted",
            entity_type="calendar_event",
            entity_id=entity_id_int(event_id),
            payload={
                "schema_version": 1,
                "source": "calendar/manual_delete",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "event_id": event_id,
                },
            },
            con=con,
        )

        return {"event_id": event_id, "tenant_id": tenant, "deleted": True}

    result = _run_write_txn(_tx)
    try:
        feed = knowledge_ics_build_local_feed(tenant)
        result["feed_path"] = str(feed.get("feed_path", ""))
    except Exception:
        result["feed_path"] = ""
    return result


def _read_task_deadlines(tenant_id: str) -> list[dict[str, Any]]:
    today = datetime.now(UTC).date()
    min_due = (today - timedelta(days=_feed_past_days())).isoformat()
    max_due = (today + timedelta(days=_feed_future_days())).isoformat()

    con: sqlite3.Connection | None = None
    try:
        if has_app_context():
            auth_db = current_app.extensions.get("auth_db")
            if auth_db is not None:
                con = auth_db._db()
        if con is None:
            with legacy_core._DB_LOCK:
                con = _db()
        rows = con.execute(
            """
            SELECT id, title, description, due_at, assigned_to
            FROM team_tasks
            WHERE tenant_id=? AND due_at IS NOT NULL
            AND due_at >= ? AND due_at <= ?
            AND status != 'CLOSED' AND status != 'REJECTED'
            """,
            (tenant_id, min_due, max_due),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()


def knowledge_calendar_events_list(
    tenant_id: str,
    *,
    start_iso: str | None = None,
    end_iso: str | None = None,
    kinds: list[str] | None = None,
    include_manual: bool = True,
    include_deadlines: bool = True,
    include_tasks: bool = True,
    owner_user_id: str | None = None,
) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    range_start = _parse_iso_datetime(start_iso) if start_iso else datetime.now(UTC) - timedelta(days=30)
    range_end = _parse_iso_datetime(end_iso) if end_iso else datetime.now(UTC) + timedelta(days=365)
    if not range_start or not range_end or range_end < range_start:
        raise ValueError("validation_error")

    wanted = {_normalize_kind(k) for k in (kinds or []) if _clean_text(k, 40)}
    out: list[dict[str, Any]] = []

    if include_manual:
        for event in _read_manual_events(tenant, owner_user_id=owner_user_id):
            occ = _expand_manual_event_occurrences(event, range_start=range_start, range_end=range_end)
            for item in occ:
                kind = _normalize_kind(item.get("kind"))
                if wanted and kind not in wanted:
                    continue
                out.append(
                    {
                        "source": "manual",
                        "event_id": item.get("event_id"),
                        "title": item.get("title"),
                        "kind": kind,
                        "all_day": bool(int(item.get("all_day", 0) or 0)),
                        "start_at": item.get("occurrence_start"),
                        "end_at": item.get("occurrence_end"),
                        "location": item.get("location", ""),
                        "notes": item.get("notes", ""),
                        "owner_user_id": item.get("owner_user_id", ""),
                        "reminder_minutes": int(item.get("reminder_minutes", 0) or 0),
                    }
                )

    if include_deadlines:
        for d in _read_ocr_deadline_events(tenant):
            due = _parse_iso_date(d.get("due_date"))
            if not due:
                continue
            start_dt = datetime(due.year, due.month, due.day, tzinfo=UTC)
            end_dt = start_dt + timedelta(days=1)
            kind = _normalize_kind(str(d.get("kind", "deadline")))
            if wanted and kind not in wanted:
                continue
            if end_dt < range_start or start_dt > range_end:
                continue
            out.append(
                {
                    "source": "deadline",
                    "event_id": _clean_text(f"deadline:{d.get('source_doc_ref', '')}:{d.get('due_date', '')}", 120),
                    "title": d.get("summary", "Deadline"),
                    "kind": kind,
                    "all_day": True,
                    "start_at": start_dt.isoformat(timespec="seconds"),
                    "end_at": end_dt.isoformat(timespec="seconds"),
                    "location": "",
                    "notes": d.get("excerpt", ""),
                    "owner_user_id": "",
                    "reminder_minutes": 24 * 60,
                }
            )

    if include_tasks:
        for t in _read_task_deadlines(tenant):
            due_str = str(t.get("due_at", ""))
            # due_at is often just "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS"
            due_dt = _parse_iso_datetime(due_str)
            if not due_dt:
                # Try date only
                d = _parse_iso_date(due_str)
                if d:
                    due_dt = datetime(d.year, d.month, d.day, tzinfo=UTC)
            
            if not due_dt:
                continue
            
            if due_dt < range_start or due_dt > range_end:
                continue
                
            out.append(
                {
                    "source": "task",
                    "event_id": f"task:{t['id']}",
                    "title": f"Aufgabe: {t['title']}",
                    "kind": "task_due",
                    "all_day": "T" not in due_str,
                    "start_at": due_dt.isoformat(timespec="seconds"),
                    "end_at": (due_dt + timedelta(hours=1)).isoformat(timespec="seconds"),
                    "location": "",
                    "notes": t.get("description", ""),
                    "owner_user_id": t.get("assigned_to", ""),
                    "reminder_minutes": 60,
                }
            )

    out.sort(key=lambda x: (str(x.get("start_at", "")), str(x.get("title", ""))))
    return out


def knowledge_calendar_reminders_due(
    tenant_id: str,
    *,
    now_iso: str | None = None,
    within_minutes: int = 60,
    owner_user_id: str | None = None,
) -> list[dict[str, Any]]:
    now = _parse_iso_datetime(now_iso) if now_iso else datetime.now(UTC)
    if not now:
        raise ValueError("validation_error")
    horizon = now + timedelta(minutes=max(1, min(int(within_minutes), 10080)))

    events = knowledge_calendar_events_list(
        tenant_id,
        start_iso=(now - timedelta(days=2)).isoformat(timespec="seconds"),
        end_iso=horizon.isoformat(timespec="seconds"),
        include_manual=True,
        include_deadlines=True,
        owner_user_id=owner_user_id,
    )

    due: list[dict[str, Any]] = []
    for ev in events:
        start_dt = _parse_iso_datetime(str(ev.get("start_at", "")))
        if not start_dt:
            continue
        minutes = max(0, min(int(ev.get("reminder_minutes", 0) or 0), 10080))
        remind_at = start_dt - timedelta(minutes=minutes)
        if now <= remind_at <= horizon:
            due.append(
                {
                    "event_id": ev.get("event_id"),
                    "title": ev.get("title"),
                    "start_at": ev.get("start_at"),
                    "remind_at": remind_at.isoformat(timespec="seconds"),
                    "kind": ev.get("kind"),
                    "source": ev.get("source"),
                }
            )
    due.sort(key=lambda x: str(x.get("remind_at", "")))
    return due


def _render_unified_ics(tenant_id: str, events: list[dict[str, Any]]) -> bytes:
    now = datetime.now(UTC)
    dtstamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KUKANILEA//Strategic Scheduling//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(f'KUKANILEA Calendar ({tenant_id})')}",
        "X-WR-TIMEZONE:UTC",
    ]

    for ev in events:
        start_dt = _parse_iso_datetime(str(ev.get("start_at", "")))
        end_dt = _parse_iso_datetime(str(ev.get("end_at", "")))
        if not start_dt or not end_dt:
            continue
        uid_seed = "|".join([tenant_id, str(ev.get("event_id", "")), str(ev.get("start_at", "")), str(ev.get("title", ""))])
        uid = f"{sha256(uid_seed.encode('utf-8')).hexdigest()[:30]}@kukanilea.local"
        title = _ics_escape(str(ev.get("title", "Event")))
        description = _ics_escape(str(ev.get("notes", "")))
        categories = _ics_escape(str(ev.get("kind", "general")).upper())

        all_day = bool(ev.get("all_day", False))
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTAMP:{dtstamp}")
        if all_day:
            lines.append(f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{end_dt.strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%SZ')}")
            lines.append(f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%SZ')}")
        lines.append(f"SUMMARY:{title}")
        if description:
            lines.append(f"DESCRIPTION:{description}")
        if ev.get("location"):
            lines.append(f"LOCATION:{_ics_escape(str(ev.get('location', '')))}")
        lines.append(f"CATEGORIES:KUKANILEA,{categories}")
        lines.append("STATUS:CONFIRMED")

        remind_minutes = max(0, min(int(ev.get("reminder_minutes", 0) or 0), 10080))
        if remind_minutes > 0:
            lines.extend(
                [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{title}",
                    f"TRIGGER:-PT{remind_minutes}M",
                    "END:VALARM",
                ]
            )
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    folded: list[str] = []
    for line in lines:
        folded.extend(_ics_fold(line))
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")


def knowledge_ics_build_local_feed(
    tenant_id: str,
    *,
    kinds: list[str] | None = None,
    include_manual: bool = True,
    include_deadlines: bool = True,
    owner_user_id: str | None = None,
    filename_suffix: str = "",
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_calendar(policy_row):
        raise ValueError("policy_blocked")

    events = knowledge_calendar_events_list(
        tenant,
        kinds=kinds,
        include_manual=include_manual,
        include_deadlines=include_deadlines,
        owner_user_id=owner_user_id,
        start_iso=(datetime.now(UTC) - timedelta(days=_feed_past_days())).isoformat(timespec="seconds"),
        end_iso=(datetime.now(UTC) + timedelta(days=_feed_future_days())).isoformat(timespec="seconds"),
    )

    payload = _render_unified_ics(tenant, events)
    base = _feed_path(tenant)
    if filename_suffix:
        safe_suffix = _slugify(filename_suffix)
        path = base.with_name(f"{base.stem}-{safe_suffix}{base.suffix}")
    else:
        path = base
    _atomic_write(path, payload)
    return {
        "tenant_id": tenant,
        "event_count": int(len(events)),
        "feed_path": str(path),
        "feed_filename": path.name,
    }


def knowledge_calendar_suggest_from_text(
    tenant_id: str,
    actor_user_id: str | None,
    text: str,
    *,
    filename_hint: str | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    suggestions = _extract_deadline_events_from_ocr_text(text, filename_hint=filename_hint)
    created: list[dict[str, Any]] = []
    if persist and suggestions:
        policy_row = knowledge_policy_get(tenant)
        if not _policy_allows_ocr_calendar(policy_row):
            return {
                "tenant_id": tenant,
                "suggestions": suggestions,
                "created": created,
            }
        for ev in suggestions:
            due = _parse_iso_date(ev.get("due_date"))
            if not due:
                continue
            created.append(
                knowledge_calendar_event_create(
                    tenant,
                    actor_user_id,
                    title=str(ev.get("summary", "Deadline")),
                    start_at=due.isoformat(),
                    end_at=(due + timedelta(days=1)).isoformat(),
                    all_day=True,
                    kind=str(ev.get("kind", "deadline")),
                    notes=str(ev.get("excerpt", "")),
                    reminder_minutes=24 * 60,
                )
            )
    return {
        "tenant_id": tenant,
        "suggestions": suggestions,
        "created": created,
    }
