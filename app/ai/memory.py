from __future__ import annotations

import json
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
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _connect() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_ai_schema() -> None:
    con = _connect()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_conversations (
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              user_message_redacted TEXT NOT NULL,
              assistant_response_redacted TEXT NOT NULL,
              tool_used_json TEXT,
              created_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_feedback (
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              conversation_id TEXT NOT NULL,
              rating TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id)
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_conversations_tenant_created ON ai_conversations(tenant_id, created_at DESC)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_feedback_tenant_created ON ai_feedback(tenant_id, created_at DESC)"
        )
        con.commit()
    finally:
        con.close()


def save_conversation(
    *,
    tenant_id: str,
    user_id: str,
    user_message: str,
    assistant_response: str,
    tools_used: list[str] | None = None,
) -> str:
    ensure_ai_schema()
    conversation_id = str(uuid.uuid4())
    now = _now_iso()
    redacted_user = knowledge_redact_text(user_message or "", max_len=2000)
    redacted_response = knowledge_redact_text(assistant_response or "", max_len=4000)
    tools_json = json.dumps(tools_used or [], ensure_ascii=False)

    con = _connect()
    try:
        con.execute(
            """
            INSERT INTO ai_conversations(
              id, tenant_id, user_id, user_message_redacted,
              assistant_response_redacted, tool_used_json, created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                conversation_id,
                str(tenant_id or ""),
                str(user_id or "system"),
                redacted_user,
                redacted_response,
                tools_json,
                now,
            ),
        )
        con.commit()
    finally:
        con.close()
    return conversation_id


def add_feedback(*, tenant_id: str, conversation_id: str, rating: str) -> str:
    ensure_ai_schema()
    rating_clean = str(rating or "").strip().lower()
    if rating_clean not in {"positive", "negative"}:
        raise ValueError("validation_error")

    con = _connect()
    try:
        row = con.execute(
            """
            SELECT id
            FROM ai_conversations
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (str(tenant_id or ""), str(conversation_id or "")),
        ).fetchone()
        if row is None:
            raise ValueError("not_found")

        feedback_id = str(uuid.uuid4())
        con.execute(
            """
            INSERT INTO ai_feedback(id, tenant_id, conversation_id, rating, created_at)
            VALUES (?,?,?,?,?)
            """,
            (
                feedback_id,
                str(tenant_id or ""),
                str(conversation_id),
                rating_clean,
                _now_iso(),
            ),
        )
        con.commit()
        return feedback_id
    finally:
        con.close()


def list_recent_conversations(
    *, tenant_id: str, user_id: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    ensure_ai_schema()
    lim = max(1, min(int(limit or 10), 100))
    con = _connect()
    try:
        if user_id:
            rows = con.execute(
                """
                SELECT id, user_message_redacted, assistant_response_redacted, tool_used_json, created_at
                FROM ai_conversations
                WHERE tenant_id=? AND user_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (str(tenant_id or ""), str(user_id), lim),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT id, user_message_redacted, assistant_response_redacted, tool_used_json, created_at
                FROM ai_conversations
                WHERE tenant_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (str(tenant_id or ""), lim),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            tools: list[str] = []
            try:
                parsed = json.loads(str(row["tool_used_json"] or "[]"))
                if isinstance(parsed, list):
                    tools = [str(v) for v in parsed[:8]]
            except Exception:
                tools = []
            out.append(
                {
                    "id": str(row["id"] or ""),
                    "user_message": str(row["user_message_redacted"] or ""),
                    "assistant_response": str(row["assistant_response_redacted"] or ""),
                    "tools_used": tools,
                    "created_at": str(row["created_at"] or ""),
                }
            )
        return out
    finally:
        con.close()
