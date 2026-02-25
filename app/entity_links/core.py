from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from flask import current_app, has_app_context

from app.core import logic as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

MAX_TYPE = 32
MAX_ID = 64
MAX_LINK_TYPE = 32

ALLOWED_TYPES = {
    "lead",
    "deal",
    "quote",
    "task",
    "project",
    "customer",
    "knowledge_note",
    "knowledge_chunk",
    "knowledge_email_source",
    "knowledge_ics_source",
}

ALLOWED_LINK_TYPES = {
    "related",
    "converted_from",
    "references",
    "attachment",
    "customer_of",
    "project_of",
}

EXISTENCE_CHECK_TYPES: dict[str, tuple[str, str, str, str | None]] = {
    "lead": ("leads", "tenant_id", "id", None),
    "deal": ("deals", "tenant_id", "id", None),
    "quote": ("quotes", "tenant_id", "id", None),
    "customer": ("customers", "tenant_id", "id", None),
    "project": ("time_projects", "tenant_id", "id", None),
    "task": ("tasks", "tenant", "id", None),
    "knowledge_chunk": ("knowledge_chunks", "tenant_id", "chunk_id", None),
    "knowledge_note": (
        "knowledge_chunks",
        "tenant_id",
        "chunk_id",
        "source_type='manual'",
    ),
    "knowledge_email_source": ("knowledge_email_sources", "tenant_id", "id", None),
}


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _norm(s: str | None, max_len: int) -> str:
    value = (s or "").replace("\x00", "").strip().lower()
    if not value or len(value) > max_len:
        raise ValueError("validation_error")
    return value


def _norm_id(s: str | None, max_len: int) -> str:
    value = (s or "").replace("\x00", "").strip()
    if not value or len(value) > max_len:
        raise ValueError("validation_error")
    return value


def canonical_pair(
    left_type: str, left_id: str, right_type: str, right_id: str
) -> tuple[str, str, str, str]:
    left_pair = (left_type, left_id)
    right_pair = (right_type, right_id)
    if left_pair <= right_pair:
        return left_type, left_id, right_type, right_id
    return right_type, right_id, left_type, left_id


def _exists_in_table(
    con: sqlite3.Connection,
    tenant_id: str,
    *,
    table: str,
    tenant_col: str,
    id_col: str,
    id_val: str,
    extra_where: str | None,
) -> bool:
    sql = f"SELECT 1 FROM {table} WHERE {tenant_col}=? AND {id_col}=?"
    params: list[Any] = [tenant_id, id_val]
    if extra_where:
        sql += f" AND {extra_where}"
    sql += " LIMIT 1"
    row = con.execute(sql, tuple(params)).fetchone()
    return bool(row)


def _validate_entity(
    con: sqlite3.Connection, tenant_id: str, entity_type: str, entity_id: str
) -> None:
    mapping = EXISTENCE_CHECK_TYPES.get(entity_type)
    if mapping is None:
        return
    table, tenant_col, id_col, extra_where = mapping
    if not _exists_in_table(
        con,
        tenant_id,
        table=table,
        tenant_col=tenant_col,
        id_col=id_col,
        id_val=entity_id,
        extra_where=extra_where,
    ):
        raise ValueError("entity_not_found")


def create_link(
    tenant_id: str,
    left_type: str,
    left_id: str,
    right_type: str,
    right_id: str,
    link_type: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    lt = _norm(left_type, MAX_TYPE)
    rt = _norm(right_type, MAX_TYPE)
    li = _norm_id(left_id, MAX_ID)
    ri = _norm_id(right_id, MAX_ID)
    ltype = _norm(link_type, MAX_LINK_TYPE)

    if lt not in ALLOWED_TYPES or rt not in ALLOWED_TYPES:
        raise ValueError("validation_error")
    if ltype not in ALLOWED_LINK_TYPES:
        raise ValueError("validation_error")
    if lt == rt and li == ri:
        raise ValueError("validation_error")

    a_type, a_id, b_type, b_id = canonical_pair(lt, li, rt, ri)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        _validate_entity(con, tenant, a_type, a_id)
        _validate_entity(con, tenant, b_type, b_id)
        row_id = _new_id()
        now = _now_iso()
        try:
            con.execute(
                """
                INSERT INTO entity_links(
                  id, tenant_id, a_type, a_id, b_type, b_id, link_type, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (row_id, tenant, a_type, a_id, b_type, b_id, ltype, now, now),
            )
        except sqlite3.IntegrityError as exc:
            msg = str(exc).lower()
            if "unique" in msg:
                raise ValueError("duplicate")
            raise

        event_append(
            event_type="entity_link_created",
            entity_type="entity_link",
            entity_id=entity_id_int(row_id),
            payload={
                "schema_version": 1,
                "source": "entity_links/create",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "link_id": row_id,
                    "a_type": a_type,
                    "a_id": a_id,
                    "b_type": b_type,
                    "b_id": b_id,
                    "link_type": ltype,
                },
            },
            con=con,
        )

        return {
            "id": row_id,
            "tenant_id": tenant,
            "a_type": a_type,
            "a_id": a_id,
            "b_type": b_type,
            "b_id": b_id,
            "link_type": ltype,
            "created_at": now,
            "updated_at": now,
        }

    return _run_write_txn(_tx)


def delete_link(tenant_id: str, link_id: str, actor_user_id: str | None = None) -> None:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    lid = _norm_id(link_id, MAX_ID)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            """
            SELECT id, a_type, a_id, b_type, b_id, link_type
            FROM entity_links
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant, lid),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        con.execute(
            "DELETE FROM entity_links WHERE tenant_id=? AND id=?", (tenant, lid)
        )

        event_append(
            event_type="entity_link_deleted",
            entity_type="entity_link",
            entity_id=entity_id_int(lid),
            payload={
                "schema_version": 1,
                "source": "entity_links/delete",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "link_id": lid,
                    "a_type": str(row["a_type"]),
                    "a_id": str(row["a_id"]),
                    "b_type": str(row["b_type"]),
                    "b_id": str(row["b_id"]),
                    "link_type": str(row["link_type"]),
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def list_links_for_entity(
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    link_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    etype = _norm(entity_type, MAX_TYPE)
    eid = _norm_id(entity_id, MAX_ID)
    ltype = _norm(link_type, MAX_LINK_TYPE) if link_type else None
    lim = max(1, min(int(limit), 100))
    off = max(0, int(offset))

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            sql = """
            SELECT
              id, tenant_id, a_type, a_id, b_type, b_id, link_type, created_at, updated_at,
              CASE WHEN a_type=? AND a_id=? THEN b_type ELSE a_type END AS other_type,
              CASE WHEN a_type=? AND a_id=? THEN b_id ELSE a_id END AS other_id
            FROM entity_links
            WHERE tenant_id=? AND ((a_type=? AND a_id=?) OR (b_type=? AND b_id=?))
            """
            params: list[Any] = [etype, eid, etype, eid, tenant, etype, eid, etype, eid]
            if ltype:
                sql += " AND link_type=?"
                params.append(ltype)
            sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
            params.extend([lim, off])
            rows = con.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
