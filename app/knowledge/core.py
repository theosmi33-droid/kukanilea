from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from flask import current_app, has_app_context

from app.core import logic as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

MAX_QUERY = 256
MAX_TITLE = 200
MAX_BODY = 8000
MAX_TAGS = 300
MAX_SOURCE_REF = 200
MAX_RESULTS = 25

SOURCE_TYPES = {
    "manual",
    "task",
    "project",
    "document",
    "email",
    "calendar",
    "lead",
    "ocr",
}

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
LONG_NUM_RE = re.compile(r"\b\d{7,}\b")
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{2,}")


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_chunk_id() -> str:
    return uuid.uuid4().hex


def _db() -> sqlite3.Connection:
    return legacy_core._db()  # type: ignore[attr-defined]


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _ensure_writable() -> None:
    if _is_read_only():
        raise PermissionError("read_only")


def _norm(s: str | None, max_len: int) -> str:
    v = (s or "").replace("\x00", "").strip()
    if len(v) > max_len:
        raise ValueError("validation_error")
    return v


def _redact(text: str) -> str:
    out = text.replace("\r", " ").replace("\n", " ")
    out = EMAIL_RE.sub("[redacted-email]", out)
    out = PHONE_RE.sub("[redacted-phone]", out)
    out = LONG_NUM_RE.sub("[redacted-number]", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def knowledge_redact_text(text: str | None, max_len: int = MAX_BODY) -> str:
    value = (text or "").replace("\x00", " ")
    if len(value) > max_len:
        value = value[:max_len]
    return _redact(value)


def _content_hash(body: str) -> str:
    return sha256(body.encode("utf-8")).hexdigest()


def _json_valid_fast(value: str) -> bool:
    try:
        json.loads(value)
    except Exception:
        return False
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            try:
                row = con.execute("SELECT json_valid(?) AS ok", (value,)).fetchone()
                return bool(row and int(row["ok"] or 0) == 1)
            except Exception:
                return True
        finally:
            con.close()


def _fts5_available(con: sqlite3.Connection | None = None) -> bool:
    def _probe(conn: sqlite3.Connection) -> bool:
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS __kb_fts_test USING fts5(x)"
            )
            conn.execute("DROP TABLE IF EXISTS __kb_fts_test")
            return True
        except Exception:
            return False

    if con is not None:
        return _probe(con)

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        own = _db()
        try:
            return _probe(own)
        finally:
            own.close()


def _policy_defaults() -> dict[str, Any]:
    return {
        "allow_manual": 1,
        "allow_tasks": 1,
        "allow_projects": 1,
        "allow_documents": 0,
        "allow_leads": 0,
        "allow_email": 0,
        "allow_calendar": 0,
        "allow_ocr": 0,
        "allow_customer_pii": 0,
    }


def knowledge_policy_get(tenant_id: str) -> dict[str, Any]:
    t = _tenant(tenant_id)
    defaults = _policy_defaults()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT tenant_id, allow_manual, allow_tasks, allow_projects, allow_documents,
                   allow_leads, allow_email, allow_calendar, allow_ocr, allow_customer_pii, updated_at
            FROM knowledge_source_policies
            WHERE tenant_id=?
            LIMIT 1
            """,
            (t,),
        ).fetchone()
        if row:
            return dict(row)
        now = _now_iso()
        con.execute(
            """
            INSERT INTO knowledge_source_policies(
              tenant_id, allow_manual, allow_tasks, allow_projects, allow_documents,
              allow_leads, allow_email, allow_calendar, allow_ocr, allow_customer_pii, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                t,
                defaults["allow_manual"],
                defaults["allow_tasks"],
                defaults["allow_projects"],
                defaults["allow_documents"],
                defaults["allow_leads"],
                defaults["allow_email"],
                defaults["allow_calendar"],
                defaults["allow_ocr"],
                defaults["allow_customer_pii"],
                now,
            ),
        )
        row2 = con.execute(
            "SELECT * FROM knowledge_source_policies WHERE tenant_id=? LIMIT 1", (t,)
        ).fetchone()
        return dict(row2) if row2 else {"tenant_id": t, **defaults, "updated_at": now}

    return _run_write_txn(_tx)


def knowledge_policy_update(
    tenant_id: str, actor_user_id: str, **flags: Any
) -> dict[str, Any]:
    _ensure_writable()
    t = _tenant(tenant_id)
    allowed_keys = {
        "allow_manual",
        "allow_tasks",
        "allow_projects",
        "allow_documents",
        "allow_leads",
        "allow_email",
        "allow_calendar",
        "allow_ocr",
        "allow_customer_pii",
    }
    patch = {k: int(bool(flags[k])) for k in flags if k in allowed_keys}
    if not patch:
        raise ValueError("validation_error")

    if patch.get("allow_customer_pii", None) == 0:
        for key in ("allow_leads", "allow_email", "allow_calendar"):
            if patch.get(key, 0) == 1:
                raise ValueError("validation_error")

    current = knowledge_policy_get(t)
    merged = {**current, **patch}
    if int(merged.get("allow_customer_pii", 0)) == 0 and (
        int(merged.get("allow_leads", 0)) == 1
        or int(merged.get("allow_email", 0)) == 1
        or int(merged.get("allow_calendar", 0)) == 1
    ):
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            UPDATE knowledge_source_policies
            SET allow_manual=?, allow_tasks=?, allow_projects=?, allow_documents=?,
                allow_leads=?, allow_email=?, allow_calendar=?, allow_ocr=?, allow_customer_pii=?, updated_at=?
            WHERE tenant_id=?
            """,
            (
                int(merged["allow_manual"]),
                int(merged["allow_tasks"]),
                int(merged["allow_projects"]),
                int(merged["allow_documents"]),
                int(merged["allow_leads"]),
                int(merged["allow_email"]),
                int(merged["allow_calendar"]),
                int(merged["allow_ocr"]),
                int(merged["allow_customer_pii"]),
                _now_iso(),
                t,
            ),
        )
        row = con.execute(
            "SELECT * FROM knowledge_source_policies WHERE tenant_id=? LIMIT 1", (t,)
        ).fetchone()
        event_append(
            event_type="knowledge_policy_updated",
            entity_type="knowledge_policy",
            entity_id=entity_id_int(t),
            payload={
                "schema_version": 1,
                "source": "knowledge/policy_update",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "allow_manual": int(merged["allow_manual"]),
                    "allow_tasks": int(merged["allow_tasks"]),
                    "allow_projects": int(merged["allow_projects"]),
                    "allow_documents": int(merged["allow_documents"]),
                    "allow_leads": int(merged["allow_leads"]),
                    "allow_email": int(merged["allow_email"]),
                    "allow_calendar": int(merged["allow_calendar"]),
                    "allow_ocr": int(merged["allow_ocr"]),
                    "allow_customer_pii": int(merged["allow_customer_pii"]),
                },
            },
            con=con,
        )
        return dict(row) if row else merged

    return _run_write_txn(_tx)


def _policy_allows(policy: dict[str, Any], source_type: str) -> bool:
    st = source_type.lower()
    if st == "manual":
        return bool(int(policy.get("allow_manual", 0)))
    if st == "task":
        return bool(int(policy.get("allow_tasks", 0)))
    if st == "project":
        return bool(int(policy.get("allow_projects", 0)))
    if st == "document":
        return bool(int(policy.get("allow_documents", 0)))
    if st == "lead":
        return bool(int(policy.get("allow_leads", 0)))
    if st == "email":
        return bool(int(policy.get("allow_email", 0)))
    if st == "calendar":
        return bool(int(policy.get("allow_calendar", 0)))
    if st == "ocr":
        return bool(int(policy.get("allow_ocr", 0)))
    return False


def _ensure_source_allowed(policy: dict[str, Any], source_type: str) -> None:
    st = source_type.lower()
    if st not in SOURCE_TYPES:
        raise ValueError("validation_error")
    if not _policy_allows(policy, st):
        raise ValueError("policy_blocked")
    if (
        st in {"lead", "email", "calendar", "document"}
        and int(policy.get("allow_customer_pii", 0)) == 0
    ):
        raise ValueError("policy_blocked")


def _fts_delete(
    con: sqlite3.Connection,
    row_id: int,
    old_title: str,
    old_body: str,
    old_tags: str,
) -> None:
    if _fts5_available(con):
        con.execute(
            "INSERT INTO knowledge_fts(knowledge_fts, rowid, title, body, tags) VALUES('delete', ?, ?, ?, ?)",
            (row_id, old_title, old_body, old_tags),
        )
    else:
        con.execute("DELETE FROM knowledge_fts_fallback WHERE rowid=?", (row_id,))


def _fts_upsert(
    con: sqlite3.Connection, row_id: int, title: str, body: str, tags: str
) -> None:
    if _fts5_available(con):
        con.execute(
            "INSERT INTO knowledge_fts(rowid, title, body, tags) VALUES (?, ?, ?, ?)",
            (row_id, title, body, tags),
        )
    else:
        con.execute(
            "INSERT OR REPLACE INTO knowledge_fts_fallback(rowid, title, body, tags) VALUES (?, ?, ?, ?)",
            (row_id, title, body, tags),
        )


def knowledge_note_create(
    tenant_id: str,
    owner_user_id: str,
    title: str,
    body: str,
    tags: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    t = _tenant(tenant_id)
    policy = knowledge_policy_get(t)
    _ensure_source_allowed(policy, "manual")

    title_n = _redact(_norm(title, MAX_TITLE))
    body_n = _redact(_norm(body, MAX_BODY))
    tags_n = _redact(_norm(tags, MAX_TAGS))
    if not body_n:
        raise ValueError("validation_error")

    chunk_id = _new_chunk_id()
    source_ref = _norm(f"manual:{chunk_id}", MAX_SOURCE_REF)
    now = _now_iso()
    c_hash = _content_hash(body_n)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        cur = con.execute(
            """
            INSERT INTO knowledge_chunks(
              chunk_id, tenant_id, owner_user_id, source_type, source_ref,
              title, body, tags, content_hash, is_redacted, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                chunk_id,
                t,
                owner_user_id or None,
                "manual",
                source_ref,
                title_n,
                body_n,
                tags_n,
                c_hash,
                1,
                now,
                now,
            ),
        )
        row_id = int(cur.lastrowid or 0)
        _fts_upsert(con, row_id, title_n, body_n, tags_n)
        event_append(
            event_type="knowledge_note_created",
            entity_type="knowledge_chunk",
            entity_id=row_id,
            payload={
                "schema_version": 1,
                "source": "knowledge/note_create",
                "actor_user_id": owner_user_id,
                "tenant_id": t,
                "data": {
                    "chunk_id": chunk_id,
                    "source_type": "manual",
                    "owner_user_id_present": bool(owner_user_id),
                },
            },
            con=con,
        )
        return {
            "chunk_id": chunk_id,
            "tenant_id": t,
            "owner_user_id": owner_user_id,
            "source_type": "manual",
            "source_ref": source_ref,
            "title": title_n,
            "body": body_n,
            "tags": tags_n,
            "is_redacted": 1,
            "created_at": now,
            "updated_at": now,
        }

    return _run_write_txn(_tx)


def knowledge_note_update(
    tenant_id: str,
    chunk_id: str,
    owner_user_id: str,
    title: str,
    body: str,
    tags: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    t = _tenant(tenant_id)

    title_n = _redact(_norm(title, MAX_TITLE))
    body_n = _redact(_norm(body, MAX_BODY))
    tags_n = _redact(_norm(tags, MAX_TAGS))
    if not body_n:
        raise ValueError("validation_error")

    now = _now_iso()
    c_hash = _content_hash(body_n)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT id, owner_user_id, title, body, tags
            FROM knowledge_chunks
            WHERE tenant_id=? AND chunk_id=? AND source_type='manual'
            LIMIT 1
            """,
            (t, chunk_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        if (
            owner_user_id
            and row["owner_user_id"]
            and str(row["owner_user_id"]) != owner_user_id
        ):
            raise ValueError("forbidden")

        row_id = int(row["id"])
        _fts_delete(
            con,
            row_id,
            str(row["title"] or ""),
            str(row["body"] or ""),
            str(row["tags"] or ""),
        )

        con.execute(
            """
            UPDATE knowledge_chunks
            SET title=?, body=?, tags=?, content_hash=?, is_redacted=1, updated_at=?
            WHERE tenant_id=? AND chunk_id=?
            """,
            (title_n, body_n, tags_n, c_hash, now, t, chunk_id),
        )
        _fts_upsert(con, row_id, title_n, body_n, tags_n)
        event_append(
            event_type="knowledge_note_updated",
            entity_type="knowledge_chunk",
            entity_id=row_id,
            payload={
                "schema_version": 1,
                "source": "knowledge/note_update",
                "actor_user_id": owner_user_id,
                "tenant_id": t,
                "data": {
                    "chunk_id": chunk_id,
                    "source_type": "manual",
                    "owner_user_id_present": bool(owner_user_id),
                },
            },
            con=con,
        )
        return {
            "chunk_id": chunk_id,
            "tenant_id": t,
            "title": title_n,
            "body": body_n,
            "tags": tags_n,
            "updated_at": now,
        }

    return _run_write_txn(_tx)


def knowledge_note_delete(tenant_id: str, chunk_id: str, owner_user_id: str) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            """
            SELECT id, owner_user_id, title, body, tags
            FROM knowledge_chunks
            WHERE tenant_id=? AND chunk_id=? AND source_type='manual'
            LIMIT 1
            """,
            (t, chunk_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        if (
            owner_user_id
            and row["owner_user_id"]
            and str(row["owner_user_id"]) != owner_user_id
        ):
            raise ValueError("forbidden")

        row_id = int(row["id"])
        _fts_delete(
            con,
            row_id,
            str(row["title"] or ""),
            str(row["body"] or ""),
            str(row["tags"] or ""),
        )
        con.execute(
            "DELETE FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=?",
            (t, chunk_id),
        )
        event_append(
            event_type="knowledge_note_deleted",
            entity_type="knowledge_chunk",
            entity_id=row_id,
            payload={
                "schema_version": 1,
                "source": "knowledge/note_delete",
                "actor_user_id": owner_user_id,
                "tenant_id": t,
                "data": {
                    "chunk_id": chunk_id,
                    "source_type": "manual",
                    "owner_user_id_present": bool(owner_user_id),
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def knowledge_document_ingest(
    tenant_id: str,
    actor_user_id: str | None,
    source_ref: str,
    title: str,
    body: str,
    tags: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    t = _tenant(tenant_id)
    policy = knowledge_policy_get(t)
    _ensure_source_allowed(policy, "document")

    source_ref_n = _norm(source_ref, MAX_SOURCE_REF)
    title_n = _redact(_norm(title, MAX_TITLE))
    body_n = _redact(_norm(body, MAX_BODY))
    tags_n = _redact(_norm(tags, MAX_TAGS))
    if not body_n:
        raise ValueError("redacted_empty")

    chunk_id = _new_chunk_id()
    now = _now_iso()
    c_hash = _content_hash(body_n)
    ref_hash = sha256(source_ref_n.encode("utf-8")).hexdigest()[:16]

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        try:
            cur = con.execute(
                """
                INSERT INTO knowledge_chunks(
                  chunk_id, tenant_id, owner_user_id, source_type, source_ref,
                  title, body, tags, content_hash, is_redacted, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    chunk_id,
                    t,
                    actor_user_id or None,
                    "document",
                    source_ref_n,
                    title_n,
                    body_n,
                    tags_n,
                    c_hash,
                    1,
                    now,
                    now,
                ),
            )
            row_id = int(cur.lastrowid or 0)
            dedup = False
        except sqlite3.IntegrityError as exc:
            if "unique" not in str(exc).lower():
                raise
            row = con.execute(
                """
                SELECT id, chunk_id, tenant_id, owner_user_id, source_type, source_ref,
                       title, body, tags, is_redacted, created_at, updated_at
                FROM knowledge_chunks
                WHERE tenant_id=? AND source_type='document' AND source_ref=? AND content_hash=?
                LIMIT 1
                """,
                (t, source_ref_n, c_hash),
            ).fetchone()
            if not row:
                raise
            return {**dict(row), "dedup": True}

        _fts_upsert(con, row_id, title_n, body_n, tags_n)
        event_append(
            event_type="knowledge_document_ingested",
            entity_type="knowledge_chunk",
            entity_id=row_id,
            payload={
                "schema_version": 1,
                "source": "knowledge/document_ingest",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "chunk_id": chunk_id,
                    "source_type": "document",
                    "source_ref_hash": ref_hash,
                    "dedup": dedup,
                },
            },
            con=con,
        )
        return {
            "chunk_id": chunk_id,
            "tenant_id": t,
            "owner_user_id": actor_user_id,
            "source_type": "document",
            "source_ref": source_ref_n,
            "title": title_n,
            "body": body_n,
            "tags": tags_n,
            "is_redacted": 1,
            "created_at": now,
            "updated_at": now,
            "dedup": False,
        }

    return _run_write_txn(_tx)


def knowledge_notes_list(
    tenant_id: str,
    owner_user_id: str | None,
    limit: int = 25,
    offset: int = 0,
) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), MAX_RESULTS))
    off = max(0, int(offset))
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            if owner_user_id:
                rows = con.execute(
                    """
                    SELECT chunk_id, source_type, source_ref, title,
                           substr(body, 1, 240) AS snippet,
                           tags, owner_user_id, created_at, updated_at
                    FROM knowledge_chunks
                    WHERE tenant_id=? AND source_type='manual' AND owner_user_id=?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (t, owner_user_id, lim, off),
                ).fetchall()
            else:
                rows = con.execute(
                    """
                    SELECT chunk_id, source_type, source_ref, title,
                           substr(body, 1, 240) AS snippet,
                           tags, owner_user_id, created_at, updated_at
                    FROM knowledge_chunks
                    WHERE tenant_id=? AND source_type='manual'
                    ORDER BY updated_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (t, lim, off),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def _normalize_query_for_match(query: str) -> str:
    q = _norm(query, MAX_QUERY)
    tokens = TOKEN_RE.findall(q)
    if not tokens:
        return ""
    terms = [f'"{t.lower()}"' for t in tokens[:12]]
    return " AND ".join(terms)


def knowledge_search(
    tenant_id: str,
    query: str,
    owner_user_id: str | None = None,
    source_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), MAX_RESULTS))
    match_q = _normalize_query_for_match(query)
    if not match_q:
        return []

    st = (source_type or "").strip().lower()
    if st and st not in SOURCE_TYPES:
        raise ValueError("validation_error")

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            if _fts5_available(con):
                clauses = ["c.tenant_id=?", "knowledge_fts MATCH ?"]
                params: list[Any] = [t, match_q]
                if owner_user_id:
                    clauses.append("c.owner_user_id=?")
                    params.append(owner_user_id)
                if st:
                    clauses.append("c.source_type=?")
                    params.append(st)

                where_sql = " AND ".join(clauses)
                rows = con.execute(
                    f"""
                    SELECT c.chunk_id, c.source_type, c.source_ref, c.title,
                           substr(snippet(knowledge_fts, 1, '', '', ' … ', 16), 1, 240) AS snippet,
                           c.tags,
                           bm25(knowledge_fts) AS score,
                           c.updated_at
                    FROM knowledge_fts
                    JOIN knowledge_chunks c ON c.id = knowledge_fts.rowid
                    WHERE {where_sql}
                    ORDER BY score ASC, c.updated_at DESC, c.id DESC
                    LIMIT ?
                    """,
                    tuple(params + [lim]),
                ).fetchall()
                return [dict(r) for r in rows]

            clauses = ["tenant_id=?"]
            params = [t]
            for tok in TOKEN_RE.findall(query)[:6]:
                clauses.append(
                    "(LOWER(title) LIKE LOWER(?) OR LOWER(body) LIKE LOWER(?) OR LOWER(tags) LIKE LOWER(?))"
                )
                like = f"%{tok}%"
                params.extend([like, like, like])
            if owner_user_id:
                clauses.append("owner_user_id=?")
                params.append(owner_user_id)
            if st:
                clauses.append("source_type=?")
                params.append(st)
            where_sql = " AND ".join(clauses)
            rows = con.execute(
                f"""
                SELECT chunk_id, source_type, source_ref, title,
                       substr(body, 1, 240) AS snippet,
                       tags,
                       0.0 AS score,
                       updated_at
                FROM knowledge_chunks
                WHERE {where_sql}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                tuple(params + [lim]),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def knowledge_fts_rebuild(tenant_id: str | None = None) -> None:
    _ensure_writable()
    t = _tenant(tenant_id) if tenant_id else None

    def _tx(con: sqlite3.Connection) -> None:
        if _fts5_available(con):
            con.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
        else:
            con.execute("DELETE FROM knowledge_fts_fallback")
            if t:
                rows = con.execute(
                    "SELECT id, title, body, tags FROM knowledge_chunks WHERE tenant_id=?",
                    (t,),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT id, title, body, tags FROM knowledge_chunks"
                ).fetchall()
            for r in rows:
                con.execute(
                    "INSERT INTO knowledge_fts_fallback(rowid, title, body, tags) VALUES (?, ?, ?, ?)",
                    (
                        int(r["id"]),
                        str(r["title"] or ""),
                        str(r["body"] or ""),
                        str(r["tags"] or ""),
                    ),
                )

    _run_write_txn(_tx)
