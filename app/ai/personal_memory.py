from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.config import Config
from app.knowledge import knowledge_redact_text


def _db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["AI_MEMORY_DB"])
    return Path(Config.AI_MEMORY_DB)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_personal_memory_schema() -> None:
    con = _connect()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_user_memory (
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              note_redacted TEXT NOT NULL,
              source TEXT NOT NULL DEFAULT 'user',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_user_memory_user_updated
            ON ai_user_memory(tenant_id, user_id, updated_at DESC)
            """
        )
        con.commit()
    finally:
        con.close()


def _normalize_note(note: str) -> str:
    clean = knowledge_redact_text(str(note or "").strip(), max_len=800)
    return str(clean or "").strip()


def add_user_note(
    *,
    tenant_id: str,
    user_id: str,
    note: str,
    source: str = "user",
) -> str:
    ensure_personal_memory_schema()
    note_clean = _normalize_note(note)
    if not note_clean:
        raise ValueError("note_required")
    now = _now_iso()
    con = _connect()
    try:
        row = con.execute(
            """
            SELECT id FROM ai_user_memory
            WHERE tenant_id=? AND user_id=? AND note_redacted=?
            LIMIT 1
            """,
            (str(tenant_id or ""), str(user_id or ""), note_clean),
        ).fetchone()
        if row is not None:
            note_id = str(row["id"] or "")
            con.execute(
                """
                UPDATE ai_user_memory
                SET updated_at=?, source=?
                WHERE id=?
                """,
                (now, str(source or "user"), note_id),
            )
            con.commit()
            return note_id

        note_id = str(uuid.uuid4())
        con.execute(
            """
            INSERT INTO ai_user_memory(
              id, tenant_id, user_id, note_redacted, source, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                note_id,
                str(tenant_id or ""),
                str(user_id or ""),
                note_clean,
                str(source or "user"),
                now,
                now,
            ),
        )
        con.commit()
        return note_id
    finally:
        con.close()


def list_user_notes(
    *,
    tenant_id: str,
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    ensure_personal_memory_schema()
    lim = max(1, min(int(limit or 20), 200))
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT id, note_redacted, source, created_at, updated_at
            FROM ai_user_memory
            WHERE tenant_id=? AND user_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (str(tenant_id or ""), str(user_id or ""), lim),
        ).fetchall()
        return [
            {
                "id": str(row["id"] or ""),
                "note": str(row["note_redacted"] or ""),
                "source": str(row["source"] or ""),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
            for row in rows
        ]
    finally:
        con.close()


def count_user_notes(*, tenant_id: str, user_id: str) -> int:
    ensure_personal_memory_schema()
    con = _connect()
    try:
        row = con.execute(
            """
            SELECT COUNT(*) AS c
            FROM ai_user_memory
            WHERE tenant_id=? AND user_id=?
            """,
            (str(tenant_id or ""), str(user_id or "")),
        ).fetchone()
        return int(row["c"] or 0) if row is not None else 0
    finally:
        con.close()


def render_user_memory_context(
    *,
    tenant_id: str,
    user_id: str,
    limit: int = 8,
    max_chars: int = 1400,
) -> str:
    notes = list_user_notes(tenant_id=tenant_id, user_id=user_id, limit=limit)
    if not notes:
        return ""
    lines: list[str] = []
    used = 0
    for row in notes:
        note = str(row.get("note") or "").strip()
        if not note:
            continue
        entry = f"- {note}"
        used += len(entry)
        if used > max(200, int(max_chars)):
            break
        lines.append(entry)
    if not lines:
        return ""
    return (
        "Persoenliche Notizen dieses Nutzers (vertrauenswuerdig, lokal gespeichert):\n"
        + "\n".join(lines)
    )
