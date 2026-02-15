from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

MAX_TAG_NAME = 64
MAX_COLOR_LEN = 7
MAX_TAGS_PER_TENANT = 5000
MAX_ASSIGNMENTS_PER_ENTITY = 50
MAX_ENTITY_ID = 128
MAX_ENTITY_TYPE = 32

ALLOWED_ENTITY_TYPES = {"knowledge_chunk"}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


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
        raise PermissionError("read_only")


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _clean_text(value: str | None, max_len: int) -> str:
    text = str(value or "")
    text = CONTROL_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        raise ValueError("validation_error")
    return text


def normalize_tag_name(name: str) -> tuple[str, str]:
    display = _clean_text(name, MAX_TAG_NAME)
    if not display:
        raise ValueError("validation_error")
    return display, display.casefold()


def validate_color(color: str | None) -> str | None:
    if color is None:
        return None
    val = _clean_text(color, MAX_COLOR_LEN)
    if not val:
        return None
    if not COLOR_RE.match(val):
        raise ValueError("validation_error")
    return val.lower()


def _validate_entity(entity_type: str, entity_id: str) -> tuple[str, str]:
    et = _clean_text(entity_type, MAX_ENTITY_TYPE).lower()
    if et not in ALLOWED_ENTITY_TYPES:
        raise ValueError("validation_error")
    eid = _clean_text(entity_id, MAX_ENTITY_ID)
    if not eid:
        raise ValueError("validation_error")
    return et, eid


def tag_create(
    tenant_id: str,
    name: str,
    color: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    display, norm = normalize_tag_name(name)
    color_v = validate_color(color)
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        cnt_row = con.execute(
            "SELECT COUNT(*) AS c FROM tags WHERE tenant_id=?",
            (tenant,),
        ).fetchone()
        if int((cnt_row["c"] if cnt_row else 0) or 0) >= MAX_TAGS_PER_TENANT:
            raise ValueError("limit_exceeded")

        tag_id = _new_id()
        try:
            con.execute(
                """
                INSERT INTO tags(id, tenant_id, name, name_norm, color, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (tag_id, tenant, display, norm, color_v, now, now),
            )
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise ValueError("duplicate")
            raise

        event_append(
            event_type="tag_created",
            entity_type="tag",
            entity_id=entity_id_int(tag_id),
            payload={
                "schema_version": 1,
                "source": "tags/tag_create",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {"tag_id": tag_id},
            },
            con=con,
        )
        return {
            "id": tag_id,
            "tenant_id": tenant,
            "name": display,
            "color": color_v,
            "created_at": now,
            "updated_at": now,
        }

    return _run_write_txn(_tx)


def tag_update(
    tenant_id: str,
    tag_id: str,
    name: str | None = None,
    color: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    tag_id_n = _clean_text(tag_id, 64)
    if not tag_id_n:
        raise ValueError("validation_error")

    patch_name = normalize_tag_name(name) if name is not None else None
    patch_color = validate_color(color) if color is not None else None

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            "SELECT id, name, name_norm, color, created_at, updated_at FROM tags WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, tag_id_n),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        next_name = str(row["name"])
        next_norm = str(row["name_norm"])
        next_color = row["color"]
        if patch_name is not None:
            next_name, next_norm = patch_name
        if color is not None:
            next_color = patch_color

        try:
            con.execute(
                """
                UPDATE tags
                SET name=?, name_norm=?, color=?, updated_at=?
                WHERE tenant_id=? AND id=?
                """,
                (next_name, next_norm, next_color, _now_iso(), tenant, tag_id_n),
            )
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise ValueError("duplicate")
            raise

        updated = con.execute(
            "SELECT id, tenant_id, name, color, created_at, updated_at FROM tags WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, tag_id_n),
        ).fetchone()
        event_append(
            event_type="tag_updated",
            entity_type="tag",
            entity_id=entity_id_int(tag_id_n),
            payload={
                "schema_version": 1,
                "source": "tags/tag_update",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {"tag_id": tag_id_n},
            },
            con=con,
        )
        return dict(updated) if updated else {}

    return _run_write_txn(_tx)


def tag_delete(
    tenant_id: str,
    tag_id: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    tag_id_n = _clean_text(tag_id, 64)
    if not tag_id_n:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT id FROM tags WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, tag_id_n),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        con.execute("DELETE FROM tags WHERE tenant_id=? AND id=?", (tenant, tag_id_n))
        event_append(
            event_type="tag_deleted",
            entity_type="tag",
            entity_id=entity_id_int(tag_id_n),
            payload={
                "schema_version": 1,
                "source": "tags/tag_delete",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {"tag_id": tag_id_n},
            },
            con=con,
        )

    _run_write_txn(_tx)


def tag_list(
    tenant_id: str,
    limit: int = 200,
    offset: int = 0,
    include_usage: bool = True,
) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    lim = max(1, min(int(limit), 500))
    off = max(0, int(offset))

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            if include_usage:
                rows = con.execute(
                    """
                    SELECT t.id, t.tenant_id, t.name, t.color, t.created_at, t.updated_at,
                           COUNT(a.id) AS usage_count
                    FROM tags t
                    LEFT JOIN tag_assignments a
                      ON a.tenant_id=t.tenant_id AND a.tag_id=t.id
                    WHERE t.tenant_id=?
                    GROUP BY t.id, t.tenant_id, t.name, t.color, t.created_at, t.updated_at
                    ORDER BY t.name_norm ASC, t.id ASC
                    LIMIT ? OFFSET ?
                    """,
                    (tenant, lim, off),
                ).fetchall()
            else:
                rows = con.execute(
                    """
                    SELECT id, tenant_id, name, color, created_at, updated_at
                    FROM tags
                    WHERE tenant_id=?
                    ORDER BY name_norm ASC, id ASC
                    LIMIT ? OFFSET ?
                    """,
                    (tenant, lim, off),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def tag_assign(
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    tag_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    et, eid = _validate_entity(entity_type, entity_id)
    tag_id_n = _clean_text(tag_id, 64)
    if not tag_id_n:
        raise ValueError("validation_error")
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        tag_row = con.execute(
            "SELECT id FROM tags WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, tag_id_n),
        ).fetchone()
        if not tag_row:
            raise ValueError("not_found")

        cnt_row = con.execute(
            "SELECT COUNT(*) AS c FROM tag_assignments WHERE tenant_id=? AND entity_type=? AND entity_id=?",
            (tenant, et, eid),
        ).fetchone()
        if int((cnt_row["c"] if cnt_row else 0) or 0) >= MAX_ASSIGNMENTS_PER_ENTITY:
            raise ValueError("limit_exceeded")

        assignment_id = _new_id()
        try:
            con.execute(
                """
                INSERT INTO tag_assignments(id, tenant_id, entity_type, entity_id, tag_id, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (assignment_id, tenant, et, eid, tag_id_n, now),
            )
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise ValueError("duplicate")
            raise

        event_append(
            event_type="tag_assigned",
            entity_type="tag_assignment",
            entity_id=entity_id_int(assignment_id),
            payload={
                "schema_version": 1,
                "source": "tags/tag_assign",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "tag_id": tag_id_n,
                    "entity_type": et,
                    "entity_id": eid,
                },
            },
            con=con,
        )
        return {
            "id": assignment_id,
            "tenant_id": tenant,
            "entity_type": et,
            "entity_id": eid,
            "tag_id": tag_id_n,
            "created_at": now,
        }

    return _run_write_txn(_tx)


def tag_unassign(
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    tag_id: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    et, eid = _validate_entity(entity_type, entity_id)
    tag_id_n = _clean_text(tag_id, 64)
    if not tag_id_n:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            """
            SELECT id FROM tag_assignments
            WHERE tenant_id=? AND entity_type=? AND entity_id=? AND tag_id=?
            LIMIT 1
            """,
            (tenant, et, eid, tag_id_n),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        assignment_id = str(row["id"])
        con.execute(
            "DELETE FROM tag_assignments WHERE tenant_id=? AND entity_type=? AND entity_id=? AND tag_id=?",
            (tenant, et, eid, tag_id_n),
        )
        event_append(
            event_type="tag_unassigned",
            entity_type="tag_assignment",
            entity_id=entity_id_int(assignment_id),
            payload={
                "schema_version": 1,
                "source": "tags/tag_unassign",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "tag_id": tag_id_n,
                    "entity_type": et,
                    "entity_id": eid,
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def tags_for_entity(
    tenant_id: str, entity_type: str, entity_id: str
) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    et, eid = _validate_entity(entity_type, entity_id)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            rows = con.execute(
                """
                SELECT t.id, t.name, t.color
                FROM tag_assignments a
                JOIN tags t ON t.tenant_id=a.tenant_id AND t.id=a.tag_id
                WHERE a.tenant_id=? AND a.entity_type=? AND a.entity_id=?
                ORDER BY t.name_norm ASC, t.id ASC
                """,
                (tenant, et, eid),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def tags_for_entities(
    tenant_id: str,
    entity_type: str,
    entity_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    tenant = _tenant(tenant_id)
    et = _clean_text(entity_type, MAX_ENTITY_TYPE).lower()
    if et not in ALLOWED_ENTITY_TYPES:
        raise ValueError("validation_error")

    cleaned_ids: list[str] = []
    for raw in entity_ids[:200]:
        eid = _clean_text(raw, MAX_ENTITY_ID)
        if eid:
            cleaned_ids.append(eid)
    if not cleaned_ids:
        return {}

    placeholders = ",".join("?" for _ in cleaned_ids)
    params: list[Any] = [tenant, et, *cleaned_ids]
    result: dict[str, list[dict[str, Any]]] = {eid: [] for eid in cleaned_ids}

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            rows = con.execute(
                f"""
                SELECT a.entity_id, t.id, t.name, t.color
                FROM tag_assignments a
                JOIN tags t ON t.tenant_id=a.tenant_id AND t.id=a.tag_id
                WHERE a.tenant_id=?
                  AND a.entity_type=?
                  AND a.entity_id IN ({placeholders})
                ORDER BY a.entity_id ASC, t.name_norm ASC, t.id ASC
                """,
                tuple(params),
            ).fetchall()
            for row in rows:
                entity_id_key = str(row["entity_id"])
                if entity_id_key not in result:
                    result[entity_id_key] = []
                result[entity_id_key].append(
                    {
                        "id": str(row["id"]),
                        "name": str(row["name"]),
                        "color": row["color"],
                    }
                )
            return result
        finally:
            con.close()
