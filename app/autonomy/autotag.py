from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.core import logic as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.tags.core import normalize_tag_name, validate_color

MAX_RULE_NAME = 80
MAX_RULES_PER_TENANT = 1000
MAX_JSON_LEN = 32_768
MAX_COND_DEPTH = 2
MAX_CONDS_PER_GROUP = 20
MAX_ACTIONS = 10
MAX_TAG_NAME = 40
MAX_PATTERN = 120
MAX_ROUTE_KEY = 64
TOKEN_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

ALLOWED_META_KEYS = {"doctype", "correspondent", "date"}
ALLOWED_CONDITION_TYPES = {
    "filename_glob",
    "ext_in",
    "meta_token_in",
    "date_between",
    "tags_any",
}
ALLOWED_ACTION_TYPES = {
    "add_tag",
    "remove_tag",
    "set_doctype",
    "set_correspondent",
}


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


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


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _clean_text(value: str | None, max_len: int) -> str:
    text = CONTROL_RE.sub(" ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        raise ValueError("validation_error")
    return text


def sanitize_rule_name(value: str) -> str:
    name = _clean_text(value, MAX_RULE_NAME)
    if not name:
        raise ValueError("validation_error")
    return name


def sanitize_token(value: str) -> str:
    token = _clean_text(value, 32).lower()
    if not TOKEN_RE.match(token):
        raise ValueError("validation_error")
    return token


def _sanitize_tag_name(value: str) -> str:
    text = _clean_text(value, MAX_TAG_NAME)
    if not text:
        raise ValueError("validation_error")
    return text


def _parse_iso_date(value: str) -> str:
    s = _clean_text(value, 10)
    if not DATE_RE.match(s):
        raise ValueError("validation_error")
    date.fromisoformat(s)
    return s


def _validate_condition_obj(obj: Any, depth: int = 0) -> dict[str, Any]:
    if depth > MAX_COND_DEPTH:
        raise ValueError("validation_error")
    if not isinstance(obj, dict):
        raise ValueError("validation_error")

    if "all" in obj or "any" in obj:
        keys = [k for k in obj.keys() if k in {"all", "any"}]
        if len(keys) != 1 or len(obj.keys()) != 1:
            raise ValueError("validation_error")
        key = keys[0]
        entries = obj.get(key)
        if (
            not isinstance(entries, list)
            or not entries
            or len(entries) > MAX_CONDS_PER_GROUP
        ):
            raise ValueError("validation_error")
        return {key: [_validate_condition_obj(item, depth + 1) for item in entries]}

    ctype = str(obj.get("type") or "").strip()
    if ctype not in ALLOWED_CONDITION_TYPES:
        raise ValueError("validation_error")

    if ctype == "filename_glob":
        if set(obj.keys()) != {"type", "pattern"}:
            raise ValueError("validation_error")
        pattern = _clean_text(obj.get("pattern"), MAX_PATTERN)
        if not pattern:
            raise ValueError("validation_error")
        return {"type": ctype, "pattern": pattern}

    if ctype == "ext_in":
        if set(obj.keys()) != {"type", "values"}:
            raise ValueError("validation_error")
        values = obj.get("values")
        if not isinstance(values, list) or not values or len(values) > 10:
            raise ValueError("validation_error")
        exts: list[str] = []
        for item in values:
            ext = _clean_text(str(item), 8).lower().lstrip(".")
            if not EXT_RE.match(ext):
                raise ValueError("validation_error")
            exts.append(ext)
        return {"type": ctype, "values": sorted(set(exts))}

    if ctype == "meta_token_in":
        if set(obj.keys()) != {"type", "key", "values"}:
            raise ValueError("validation_error")
        key = _clean_text(obj.get("key"), 20).lower()
        if key not in ALLOWED_META_KEYS:
            raise ValueError("validation_error")
        values = obj.get("values")
        if not isinstance(values, list) or not values or len(values) > 20:
            raise ValueError("validation_error")
        out_values: list[str] = []
        for item in values:
            if key == "date":
                out_values.append(_parse_iso_date(str(item)))
            else:
                out_values.append(sanitize_token(str(item)))
        return {"type": ctype, "key": key, "values": sorted(set(out_values))}

    if ctype == "date_between":
        if set(obj.keys()) != {"type", "start", "end"}:
            raise ValueError("validation_error")
        start = _parse_iso_date(str(obj.get("start") or ""))
        end = _parse_iso_date(str(obj.get("end") or ""))
        if start > end:
            raise ValueError("validation_error")
        return {"type": ctype, "start": start, "end": end}

    if ctype == "tags_any":
        if set(obj.keys()) != {"type", "tag_names"}:
            raise ValueError("validation_error")
        tag_names = obj.get("tag_names")
        if not isinstance(tag_names, list) or not tag_names or len(tag_names) > 20:
            raise ValueError("validation_error")
        names: list[str] = []
        for item in tag_names:
            names.append(_sanitize_tag_name(str(item)).casefold())
        return {"type": ctype, "tag_names": sorted(set(names))}

    raise ValueError("validation_error")


def _validate_actions(actions: Any) -> list[dict[str, Any]]:
    if not isinstance(actions, list) or not actions or len(actions) > MAX_ACTIONS:
        raise ValueError("validation_error")

    out: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValueError("validation_error")
        atype = str(raw.get("type") or "").strip()
        if atype not in ALLOWED_ACTION_TYPES:
            raise ValueError("validation_error")

        if atype == "add_tag":
            if set(raw.keys()) - {"type", "tag_name", "tag_color"}:
                raise ValueError("validation_error")
            tag_name = _sanitize_tag_name(str(raw.get("tag_name") or ""))
            color = validate_color(raw.get("tag_color")) if "tag_color" in raw else None
            out.append({"type": atype, "tag_name": tag_name, "tag_color": color})
            continue

        if atype == "remove_tag":
            if set(raw.keys()) != {"type", "tag_name"}:
                raise ValueError("validation_error")
            tag_name = _sanitize_tag_name(str(raw.get("tag_name") or ""))
            out.append({"type": atype, "tag_name": tag_name})
            continue

        if atype == "set_doctype":
            if set(raw.keys()) != {"type", "token"}:
                raise ValueError("validation_error")
            out.append(
                {"type": atype, "token": sanitize_token(str(raw.get("token") or ""))}
            )
            continue

        if atype == "set_correspondent":
            if set(raw.keys()) != {"type", "token"}:
                raise ValueError("validation_error")
            out.append(
                {"type": atype, "token": sanitize_token(str(raw.get("token") or ""))}
            )
            continue

        raise ValueError("validation_error")

    return out


def _canonical_json(data: Any) -> str:
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(text.encode("utf-8")) > MAX_JSON_LEN:
        raise ValueError("validation_error")
    return text


def _condition_types(cond_obj: dict[str, Any]) -> list[str]:
    out: set[str] = set()

    def _walk(node: dict[str, Any]) -> None:
        if "all" in node:
            for item in node["all"]:
                _walk(item)
            return
        if "any" in node:
            for item in node["any"]:
                _walk(item)
            return
        out.add(str(node.get("type") or ""))

    _walk(cond_obj)
    return sorted(t for t in out if t)


def _action_types(actions: list[dict[str, Any]]) -> list[str]:
    return sorted({str(a.get("type") or "") for a in actions if a.get("type")})


def autotag_rule_create(
    tenant_id: str,
    name: str,
    priority: int,
    condition_obj: dict[str, Any],
    action_list: list[dict[str, Any]],
    actor_user_id: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    rule_name = sanitize_rule_name(name)
    cond = _validate_condition_obj(condition_obj)
    actions = _validate_actions(action_list)
    prio = max(-100, min(int(priority), 100))
    enabled_i = 1 if bool(enabled) else 0
    now = _now_iso()

    cond_json = _canonical_json(cond)
    action_json = _canonical_json(actions)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        cnt = con.execute(
            "SELECT COUNT(*) AS c FROM auto_tagging_rules WHERE tenant_id=?",
            (tenant,),
        ).fetchone()
        if int((cnt["c"] if cnt else 0) or 0) >= MAX_RULES_PER_TENANT:
            raise ValueError("limit_exceeded")

        rule_id = _new_id()
        try:
            con.execute(
                """
                INSERT INTO auto_tagging_rules(
                  id, tenant_id, name, enabled, priority, condition_json, action_json, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    rule_id,
                    tenant,
                    rule_name,
                    enabled_i,
                    prio,
                    cond_json,
                    action_json,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise ValueError("duplicate")
            raise

        event_append(
            event_type="autotag_rule_created",
            entity_type="autotag_rule",
            entity_id=entity_id_int(rule_id),
            payload={
                "schema_version": 1,
                "source": "autonomy/autotag_rule_create",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "rule_id": rule_id,
                    "priority": prio,
                    "enabled": enabled_i,
                    "condition_types": _condition_types(cond),
                    "action_types": _action_types(actions),
                },
            },
            con=con,
        )
        return {
            "id": rule_id,
            "tenant_id": tenant,
            "name": rule_name,
            "enabled": enabled_i,
            "priority": prio,
            "condition_json": cond_json,
            "action_json": action_json,
            "created_at": now,
            "updated_at": now,
        }

    return _run_write_txn(_tx)


def autotag_rule_update(
    tenant_id: str,
    rule_id: str,
    *,
    name: str | None = None,
    priority: int | None = None,
    condition_obj: dict[str, Any] | None = None,
    action_list: list[dict[str, Any]] | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    rule_id_n = _clean_text(rule_id, 64)
    if not rule_id_n:
        raise ValueError("validation_error")

    cond = _validate_condition_obj(condition_obj) if condition_obj is not None else None
    actions = _validate_actions(action_list) if action_list is not None else None

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT id, name, enabled, priority, condition_json, action_json, created_at, updated_at
            FROM auto_tagging_rules
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant, rule_id_n),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        next_name = sanitize_rule_name(name) if name is not None else str(row["name"])
        next_prio = (
            max(-100, min(int(priority), 100))
            if priority is not None
            else int(row["priority"])
        )
        next_cond_json = (
            _canonical_json(cond) if cond is not None else str(row["condition_json"])
        )
        next_action_json = (
            _canonical_json(actions) if actions is not None else str(row["action_json"])
        )

        try:
            con.execute(
                """
                UPDATE auto_tagging_rules
                SET name=?, priority=?, condition_json=?, action_json=?, updated_at=?
                WHERE tenant_id=? AND id=?
                """,
                (
                    next_name,
                    next_prio,
                    next_cond_json,
                    next_action_json,
                    _now_iso(),
                    tenant,
                    rule_id_n,
                ),
            )
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower():
                raise ValueError("duplicate")
            raise

        cond_types = _condition_types(json.loads(next_cond_json))
        action_types = _action_types(json.loads(next_action_json))

        event_append(
            event_type="autotag_rule_updated",
            entity_type="autotag_rule",
            entity_id=entity_id_int(rule_id_n),
            payload={
                "schema_version": 1,
                "source": "autonomy/autotag_rule_update",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "rule_id": rule_id_n,
                    "priority": next_prio,
                    "enabled": int(row["enabled"]),
                    "condition_types": cond_types,
                    "action_types": action_types,
                },
            },
            con=con,
        )

        updated = con.execute(
            """
            SELECT id, tenant_id, name, enabled, priority, condition_json, action_json, created_at, updated_at
            FROM auto_tagging_rules
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant, rule_id_n),
        ).fetchone()
        return dict(updated) if updated else {}

    return _run_write_txn(_tx)


def autotag_rule_toggle(
    tenant_id: str,
    rule_id: str,
    enabled: bool,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    rule_id_n = _clean_text(rule_id, 64)
    enabled_i = 1 if bool(enabled) else 0

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            "SELECT id, priority, condition_json, action_json FROM auto_tagging_rules WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, rule_id_n),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        con.execute(
            "UPDATE auto_tagging_rules SET enabled=?, updated_at=? WHERE tenant_id=? AND id=?",
            (enabled_i, _now_iso(), tenant, rule_id_n),
        )
        event_append(
            event_type="autotag_rule_toggled",
            entity_type="autotag_rule",
            entity_id=entity_id_int(rule_id_n),
            payload={
                "schema_version": 1,
                "source": "autonomy/autotag_rule_toggle",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "rule_id": rule_id_n,
                    "priority": int(row["priority"]),
                    "enabled": enabled_i,
                    "condition_types": _condition_types(
                        json.loads(str(row["condition_json"]))
                    ),
                    "action_types": _action_types(json.loads(str(row["action_json"]))),
                },
            },
            con=con,
        )
        updated = con.execute(
            "SELECT id, tenant_id, name, enabled, priority, condition_json, action_json, created_at, updated_at FROM auto_tagging_rules WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, rule_id_n),
        ).fetchone()
        return dict(updated) if updated else {}

    return _run_write_txn(_tx)


def autotag_rule_delete(
    tenant_id: str,
    rule_id: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    rule_id_n = _clean_text(rule_id, 64)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT id, priority, enabled, condition_json, action_json FROM auto_tagging_rules WHERE tenant_id=? AND id=? LIMIT 1",
            (tenant, rule_id_n),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        con.execute(
            "DELETE FROM auto_tagging_rules WHERE tenant_id=? AND id=?",
            (tenant, rule_id_n),
        )
        event_append(
            event_type="autotag_rule_deleted",
            entity_type="autotag_rule",
            entity_id=entity_id_int(rule_id_n),
            payload={
                "schema_version": 1,
                "source": "autonomy/autotag_rule_delete",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "rule_id": rule_id_n,
                    "priority": int(row["priority"]),
                    "enabled": int(row["enabled"]),
                    "condition_types": _condition_types(
                        json.loads(str(row["condition_json"]))
                    ),
                    "action_types": _action_types(json.loads(str(row["action_json"]))),
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def autotag_rules_list(tenant_id: str) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            rows = con.execute(
                """
                SELECT id, tenant_id, name, enabled, priority, condition_json, action_json, created_at, updated_at
                FROM auto_tagging_rules
                WHERE tenant_id=?
                ORDER BY priority DESC, id ASC
                """,
                (tenant,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def _eval_leaf(cond: dict[str, Any], ctx: dict[str, Any]) -> bool:
    ctype = str(cond.get("type") or "")
    if ctype == "filename_glob":
        basename = str(ctx.get("filename_basename") or "")
        pattern = str(cond.get("pattern") or "")
        return bool(Path(basename).match(pattern))

    if ctype == "ext_in":
        ext = str(ctx.get("ext") or "")
        return ext in set(cond.get("values") or [])

    if ctype == "meta_token_in":
        key = str(cond.get("key") or "")
        values = set(cond.get("values") or [])
        if key == "doctype":
            target = str(ctx.get("doctype") or "")
            return target in values
        if key == "correspondent":
            target = str(ctx.get("correspondent") or "")
            return target in values
        if key == "date":
            target = str(ctx.get("date_iso") or "")
            return target in values
        return False

    if ctype == "date_between":
        date_iso = str(ctx.get("date_iso") or "")
        if not DATE_RE.match(date_iso):
            return False
        return str(cond.get("start") or "") <= date_iso <= str(cond.get("end") or "")

    if ctype == "tags_any":
        existing = set(ctx.get("tag_names") or [])
        return any(tag in existing for tag in (cond.get("tag_names") or []))

    return False


def _eval_condition(cond: dict[str, Any], ctx: dict[str, Any]) -> bool:
    if "all" in cond:
        return all(_eval_condition(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(c, ctx) for c in cond["any"])
    return _eval_leaf(cond, ctx)


def _tag_lookup(
    con: sqlite3.Connection, tenant_id: str, name_norm: str
) -> sqlite3.Row | None:
    return con.execute(
        "SELECT id, name, color FROM tags WHERE tenant_id=? AND name_norm=? LIMIT 1",
        (tenant_id, name_norm),
    ).fetchone()


def _ensure_tag(
    con: sqlite3.Connection,
    tenant_id: str,
    tag_name: str,
    tag_color: str | None,
    actor_user_id: str | None,
) -> str:
    display, norm = normalize_tag_name(tag_name)
    row = _tag_lookup(con, tenant_id, norm)
    if row:
        return str(row["id"])

    tag_id = _new_id()
    now = _now_iso()
    color = validate_color(tag_color)
    con.execute(
        "INSERT INTO tags(id, tenant_id, name, name_norm, color, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (tag_id, tenant_id, display, norm, color, now, now),
    )
    event_append(
        event_type="tag_created",
        entity_type="tag",
        entity_id=entity_id_int(tag_id),
        payload={
            "schema_version": 1,
            "source": "autonomy/autotag",
            "actor_user_id": actor_user_id,
            "tenant_id": tenant_id,
            "data": {"tag_id": tag_id},
        },
        con=con,
    )
    return tag_id


def _assign_tag(
    con: sqlite3.Connection,
    tenant_id: str,
    chunk_id: str,
    tag_id: str,
    actor_user_id: str | None,
) -> bool:
    existing = con.execute(
        "SELECT id FROM tag_assignments WHERE tenant_id=? AND entity_type='knowledge_chunk' AND entity_id=? AND tag_id=? LIMIT 1",
        (tenant_id, chunk_id, tag_id),
    ).fetchone()
    if existing:
        return False

    assignment_id = _new_id()
    con.execute(
        "INSERT INTO tag_assignments(id, tenant_id, entity_type, entity_id, tag_id, created_at) VALUES (?,?,?,?,?,?)",
        (assignment_id, tenant_id, "knowledge_chunk", chunk_id, tag_id, _now_iso()),
    )
    event_append(
        event_type="tag_assigned",
        entity_type="tag_assignment",
        entity_id=entity_id_int(assignment_id),
        payload={
            "schema_version": 1,
            "source": "autonomy/autotag",
            "actor_user_id": actor_user_id,
            "tenant_id": tenant_id,
            "data": {
                "tag_id": tag_id,
                "entity_type": "knowledge_chunk",
                "entity_id": chunk_id,
            },
        },
        con=con,
    )
    return True


def _remove_tag(
    con: sqlite3.Connection,
    tenant_id: str,
    chunk_id: str,
    tag_name: str,
    actor_user_id: str | None,
) -> bool:
    _display, norm = normalize_tag_name(tag_name)
    tag = _tag_lookup(con, tenant_id, norm)
    if not tag:
        return False
    tag_id = str(tag["id"])
    row = con.execute(
        "SELECT id FROM tag_assignments WHERE tenant_id=? AND entity_type='knowledge_chunk' AND entity_id=? AND tag_id=? LIMIT 1",
        (tenant_id, chunk_id, tag_id),
    ).fetchone()
    if not row:
        return False
    assignment_id = str(row["id"])
    con.execute(
        "DELETE FROM tag_assignments WHERE tenant_id=? AND entity_type='knowledge_chunk' AND entity_id=? AND tag_id=?",
        (tenant_id, chunk_id, tag_id),
    )
    event_append(
        event_type="tag_unassigned",
        entity_type="tag_assignment",
        entity_id=entity_id_int(assignment_id),
        payload={
            "schema_version": 1,
            "source": "autonomy/autotag",
            "actor_user_id": actor_user_id,
            "tenant_id": tenant_id,
            "data": {
                "tag_id": tag_id,
                "entity_type": "knowledge_chunk",
                "entity_id": chunk_id,
            },
        },
        con=con,
    )
    return True


def _resolve_existing_tags(
    con: sqlite3.Connection, tenant_id: str, chunk_id: str
) -> set[str]:
    rows = con.execute(
        """
        SELECT t.name_norm
        FROM tag_assignments a
        JOIN tags t ON t.tenant_id=a.tenant_id AND t.id=a.tag_id
        WHERE a.tenant_id=? AND a.entity_type='knowledge_chunk' AND a.entity_id=?
        """,
        (tenant_id, chunk_id),
    ).fetchall()
    return {str(r["name_norm"]) for r in rows}


def _resolve_source_file_chunk(
    con: sqlite3.Connection, tenant_id: str, row: sqlite3.Row
) -> str | None:
    chunk = str(row["knowledge_chunk_id"] or "")
    if chunk:
        exists = con.execute(
            "SELECT 1 FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
            (tenant_id, chunk),
        ).fetchone()
        if exists:
            return chunk

    source_kind = str(row["source_kind"] or "")
    path_hash = str(row["path_hash"] or "")
    source_ref = ""
    if source_kind == "document" and path_hash:
        source_ref = f"document:{path_hash}"

    if source_ref:
        row2 = con.execute(
            """
            SELECT chunk_id
            FROM knowledge_chunks
            WHERE tenant_id=? AND source_ref=?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (tenant_id, source_ref),
        ).fetchone()
        if row2:
            return str(row2["chunk_id"])
    return None


def autotag_apply_for_source_file(
    tenant_id: str,
    source_file_id: str,
    actor_user_id: str | None = None,
    route_key: str = "source_scan",
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    file_id = _clean_text(source_file_id, 64)
    if not file_id:
        raise ValueError("validation_error")
    route = _clean_text(route_key, MAX_ROUTE_KEY)
    if not route:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT id, source_kind, basename, metadata_json, knowledge_chunk_id,
                   doctype_token, correspondent_token
            FROM source_files
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant, file_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        chunk_id = _resolve_source_file_chunk(con, tenant, row)
        if not chunk_id:
            return {
                "ok": True,
                "applied": False,
                "reason": "no_chunk",
                "source_file_id": file_id,
            }

        metadata_raw = str(row["metadata_json"] or "")
        if len(metadata_raw.encode("utf-8")) > 8192:
            metadata_raw = "{}"
        try:
            metadata = json.loads(metadata_raw or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except Exception:
            metadata = {}

        basename = str(row["basename"] or "")
        ext = Path(basename).suffix.lower().lstrip(".") if basename else ""
        doctype = str(row["doctype_token"] or metadata.get("doctype") or "")
        correspondent = str(
            row["correspondent_token"]
            or metadata.get("correspondent_token")
            or metadata.get("customer_token")
            or ""
        )
        date_iso = str(metadata.get("date_iso") or "")

        if doctype:
            try:
                doctype = sanitize_token(doctype)
            except ValueError:
                doctype = ""
        if correspondent:
            try:
                correspondent = sanitize_token(correspondent)
            except ValueError:
                correspondent = ""
        if date_iso and not DATE_RE.match(date_iso):
            date_iso = ""

        existing_tag_names = _resolve_existing_tags(con, tenant, chunk_id)

        rules = con.execute(
            """
            SELECT id, priority, condition_json, action_json
            FROM auto_tagging_rules
            WHERE tenant_id=? AND enabled=1
            ORDER BY priority DESC, id ASC
            """,
            (tenant,),
        ).fetchall()

        applied_rule_ids: list[str] = []
        applied_action_types: list[str] = []
        tokens_changed = False
        next_doctype = doctype
        next_correspondent = correspondent

        for rule in rules:
            try:
                cond = json.loads(str(rule["condition_json"] or "{}"))
                actions = json.loads(str(rule["action_json"] or "[]"))
            except Exception:
                continue

            ctx = {
                "filename_basename": basename.casefold(),
                "ext": ext,
                "doctype": next_doctype,
                "correspondent": next_correspondent,
                "date_iso": date_iso,
                "tag_names": set(existing_tag_names),
            }
            if not _eval_condition(cond, ctx):
                continue

            rule_applied = False
            for action in actions:
                atype = str(action.get("type") or "")
                if atype == "add_tag":
                    tag_id = _ensure_tag(
                        con,
                        tenant,
                        str(action.get("tag_name") or ""),
                        action.get("tag_color"),
                        actor_user_id,
                    )
                    changed = _assign_tag(con, tenant, chunk_id, tag_id, actor_user_id)
                    if changed:
                        existing_tag_names.add(
                            normalize_tag_name(str(action.get("tag_name") or ""))[1]
                        )
                    rule_applied = rule_applied or changed
                    applied_action_types.append(atype)
                    continue

                if atype == "remove_tag":
                    changed = _remove_tag(
                        con,
                        tenant,
                        chunk_id,
                        str(action.get("tag_name") or ""),
                        actor_user_id,
                    )
                    rule_applied = rule_applied or changed
                    applied_action_types.append(atype)
                    continue

                if atype == "set_doctype":
                    token = sanitize_token(str(action.get("token") or ""))
                    if next_doctype != token:
                        next_doctype = token
                        tokens_changed = True
                        rule_applied = True
                    applied_action_types.append(atype)
                    continue

                if atype == "set_correspondent":
                    token = sanitize_token(str(action.get("token") or ""))
                    if next_correspondent != token:
                        next_correspondent = token
                        tokens_changed = True
                        rule_applied = True
                    applied_action_types.append(atype)
                    continue

            if rule_applied:
                applied_rule_ids.append(str(rule["id"]))

        now = _now_iso()
        con.execute(
            """
            UPDATE source_files
            SET knowledge_chunk_id=?, doctype_token=?, correspondent_token=?, autotag_applied_at=?
            WHERE tenant_id=? AND id=?
            """,
            (
                chunk_id,
                next_doctype or None,
                next_correspondent or None,
                now,
                tenant,
                file_id,
            ),
        )
        if tokens_changed:
            con.execute(
                """
                UPDATE knowledge_chunks
                SET doctype_token=?, correspondent_token=?, updated_at=?
                WHERE tenant_id=? AND chunk_id=?
                """,
                (
                    next_doctype or None,
                    next_correspondent or None,
                    now,
                    tenant,
                    chunk_id,
                ),
            )

        event_append(
            event_type="autotag_applied",
            entity_type="source_file",
            entity_id=entity_id_int(file_id),
            payload={
                "schema_version": 1,
                "source": "autonomy/autotag_apply",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant,
                "data": {
                    "source_file_id": file_id,
                    "knowledge_chunk_id": chunk_id,
                    "rule_ids_applied": applied_rule_ids,
                    "action_types_applied": sorted(set(applied_action_types)),
                    "route_key": route,
                },
            },
            con=con,
        )

        return {
            "ok": True,
            "applied": bool(applied_rule_ids),
            "source_file_id": file_id,
            "knowledge_chunk_id": chunk_id,
            "rules_applied": applied_rule_ids,
            "action_types": sorted(set(applied_action_types)),
            "doctype_token": next_doctype,
            "correspondent_token": next_correspondent,
        }

    return _run_write_txn(_tx)
