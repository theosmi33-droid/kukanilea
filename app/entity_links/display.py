from __future__ import annotations

import re
import sqlite3
from typing import Any

CTRL_RE = re.compile(r"[\x00-\x1f]+")
WS_RE = re.compile(r"\s+")
EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def sanitize_title(text: str, max_len: int = 80) -> str:
    value = str(text or "")
    value = value.replace("\r", " ").replace("\n", " ").replace("\x00", " ")
    value = CTRL_RE.sub(" ", value)
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    value = WS_RE.sub(" ", value).strip()
    if len(value) > max_len:
        value = value[:max_len].rstrip()
    return value or "(ohne Titel)"


def _fallback(entity_type: str, entity_id: str) -> dict[str, str]:
    t = sanitize_title(entity_type, 32)
    i = sanitize_title(entity_id, 64)
    return {
        "type": t,
        "id": i,
        "title": "(unbekannt)",
        "subtitle": "",
        "href": "",
    }


def _safe_row(con: sqlite3.Connection, sql: str, params: tuple[Any, ...]):
    try:
        return con.execute(sql, params).fetchone()
    except Exception:
        return None


def entity_display_title(
    con: sqlite3.Connection, tenant_id: str, entity_type: str, entity_id: str
) -> dict[str, str]:
    et = sanitize_title((entity_type or "").lower(), 32)
    eid = sanitize_title(entity_id, 64)

    if et == "lead":
        row = _safe_row(
            con,
            "SELECT subject, status FROM leads WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(row["subject"] or "Lead", 80),
                "subtitle": sanitize_title(row["status"] or "", 40),
                "href": f"/leads/{entity_id}",
            }
        return _fallback(et, eid)

    if et == "task":
        row = _safe_row(
            con,
            "SELECT id, title, status FROM tasks WHERE tenant=? AND id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(f"#{row['id']} {row['title'] or ''}", 80),
                "subtitle": sanitize_title(row["status"] or "", 40),
                "href": f"/tasks/{row['id']}",
            }
        return _fallback(et, eid)

    if et == "deal":
        row = _safe_row(
            con,
            "SELECT title, stage FROM deals WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(row["title"] or "Deal", 80),
                "subtitle": sanitize_title(row["stage"] or "", 40),
                "href": "",
            }
        return _fallback(et, eid)

    if et == "quote":
        row = _safe_row(
            con,
            "SELECT quote_number, status FROM quotes WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(row["quote_number"] or "Quote", 80),
                "subtitle": sanitize_title(row["status"] or "", 40),
                "href": f"/crm/quotes/{entity_id}",
            }
        return _fallback(et, eid)

    if et == "project":
        row = _safe_row(
            con,
            "SELECT name, status FROM time_projects WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(row["name"] or "Project", 80),
                "subtitle": sanitize_title(row["status"] or "", 40),
                "href": "",
            }
        return _fallback(et, eid)

    if et == "knowledge_note":
        row = _safe_row(
            con,
            """
            SELECT title, body
            FROM knowledge_chunks
            WHERE tenant_id=? AND chunk_id=? AND source_type='manual'
            LIMIT 1
            """,
            (tenant_id, entity_id),
        )
        if row:
            first_line = str(row["body"] or "").split("\n", 1)[0]
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(row["title"] or first_line or "Note", 80),
                "subtitle": "Note",
                "href": "/knowledge/notes",
            }
        return _fallback(et, eid)

    if et == "knowledge_chunk":
        row = _safe_row(
            con,
            "SELECT title, source_type FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": sanitize_title(row["title"] or "Chunk", 80),
                "subtitle": sanitize_title(row["source_type"] or "", 40),
                "href": "/knowledge",
            }
        return _fallback(et, eid)

    if et in {"knowledge_email", "knowledge_email_source"}:
        row = _safe_row(
            con,
            "SELECT id FROM knowledge_email_sources WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant_id, entity_id),
        )
        if row:
            return {
                "type": et,
                "id": eid,
                "title": "Email (.eml)",
                "subtitle": "Email",
                "href": "/knowledge/email/upload",
            }
        return _fallback(et, eid)

    return _fallback(et, eid)
