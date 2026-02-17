from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import kukanilea_core_v3_fixed as core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

from .types import (
    AutomationComponent,
    AutomationComponentInput,
    AutomationRuleRecord,
    AutomationRuleSummary,
)

RULE_TABLE = "automation_builder_rules"
TRIGGER_TABLE = "automation_builder_triggers"
CONDITION_TABLE = "automation_builder_conditions"
ACTION_TABLE = "automation_builder_actions"
EXECUTION_LOG_TABLE = "automation_builder_execution_log"
STATE_TABLE = "automation_builder_state"
PENDING_ACTION_TABLE = "automation_builder_pending_actions"


def _now_rfc3339() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _new_id() -> str:
    return str(uuid.uuid4())


def _resolve_db_path(db_path: Path | str | None) -> Path:
    if db_path is None:
        return Path(core.DB_PATH)
    return Path(db_path)


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    con.execute("PRAGMA busy_timeout=5000;")
    return con


def _table_columns(con: sqlite3.Connection, table_name: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(r["name"]) for r in rows}


def _ensure_column(con: sqlite3.Connection, table_name: str, column_def: str) -> None:
    column_name = str(column_def.split()[0]).strip()
    if column_name in _table_columns(con, table_name):
        return
    con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")


def _norm_tenant(tenant_id: str) -> str:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("validation_error")
    return tenant


def _norm_name(name: str) -> str:
    value = str(name or "").strip()
    if not value or len(value) > 200:
        raise ValueError("validation_error")
    return value


def _norm_description(description: str) -> str:
    value = str(description or "").strip()
    if len(value) > 2000:
        raise ValueError("validation_error")
    return value


def _json_canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_config(raw: Any) -> Any:
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw
    return {} if parsed is None else parsed


def _normalize_component(
    item: AutomationComponentInput | Mapping[str, Any], type_key: str
) -> tuple[str, str]:
    if not isinstance(item, Mapping):
        raise ValueError("validation_error")
    component_type = str(item.get(type_key) or item.get("type") or "").strip()
    if not component_type or len(component_type) > 120:
        raise ValueError("validation_error")
    raw_config = item.get("config")
    if raw_config is None and "config_json" in item:
        raw_config = item.get("config_json")
    if raw_config is None:
        skip = {
            "id",
            "type",
            "trigger_type",
            "condition_type",
            "action_type",
            "created_at",
            "updated_at",
        }
        raw_config = {k: v for k, v in item.items() if k not in skip}
    config = _parse_config(raw_config)
    return component_type, _json_canonical(config)


def _normalize_components(
    items: Sequence[AutomationComponentInput | Mapping[str, Any]] | None, type_key: str
) -> list[tuple[str, str]]:
    if items is None:
        return []
    out: list[tuple[str, str]] = []
    for item in items:
        out.append(_normalize_component(item, type_key))
    return out


def _event(
    *,
    event_type: str,
    rule_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> None:
    try:
        event_append(
            event_type=event_type,
            entity_type="automation_rule",
            entity_id=entity_id_int(rule_id),
            payload={"rule_id": rule_id, "tenant_id": tenant_id, **payload},
        )
    except Exception:
        return


def ensure_automation_schema(db_path: Path | str | None = None) -> None:
    path = _resolve_db_path(db_path)
    con = _connect(path)
    try:
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {RULE_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0,1)),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TRIGGER_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              trigger_type TEXT NOT NULL,
              config_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(rule_id) REFERENCES {RULE_TABLE}(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CONDITION_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              condition_type TEXT NOT NULL,
              config_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(rule_id) REFERENCES {RULE_TABLE}(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {ACTION_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              config_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(rule_id) REFERENCES {RULE_TABLE}(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {EXECUTION_LOG_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              trigger_type TEXT NOT NULL,
              trigger_ref TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT NOT NULL DEFAULT '',
              error_redacted TEXT NOT NULL DEFAULT '',
              output_redacted TEXT NOT NULL DEFAULT '',
              FOREIGN KEY(rule_id) REFERENCES {RULE_TABLE}(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {STATE_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              source TEXT NOT NULL,
              cursor TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(tenant_id, source)
            )
            """
        )
        con.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PENDING_ACTION_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              action_config TEXT NOT NULL,
              context_snapshot TEXT NOT NULL,
              created_at TEXT NOT NULL,
              confirmed_at TEXT,
              FOREIGN KEY(rule_id) REFERENCES {RULE_TABLE}(id) ON DELETE CASCADE
            )
            """
        )
        _ensure_column(con, EXECUTION_LOG_TABLE, "trigger_ref TEXT NOT NULL DEFAULT ''")
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{RULE_TABLE}_tenant_enabled ON {RULE_TABLE}(tenant_id, is_enabled)"
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{TRIGGER_TABLE}_tenant_rule ON {TRIGGER_TABLE}(tenant_id, rule_id)"
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{CONDITION_TABLE}_tenant_rule ON {CONDITION_TABLE}(tenant_id, rule_id)"
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{ACTION_TABLE}_tenant_rule ON {ACTION_TABLE}(tenant_id, rule_id)"
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{EXECUTION_LOG_TABLE}_tenant_rule_started ON {EXECUTION_LOG_TABLE}(tenant_id, rule_id, started_at)"
        )
        con.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{EXECUTION_LOG_TABLE}_unique ON {EXECUTION_LOG_TABLE}(tenant_id, rule_id, trigger_ref)"
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{STATE_TABLE}_tenant_source ON {STATE_TABLE}(tenant_id, source)"
        )
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{PENDING_ACTION_TABLE}_tenant_created ON {PENDING_ACTION_TABLE}(tenant_id, created_at DESC)"
        )
        con.commit()
    finally:
        con.close()


def _insert_children(
    con: sqlite3.Connection,
    *,
    table_name: str,
    kind_column: str,
    tenant_id: str,
    rule_id: str,
    rows: list[tuple[str, str]],
    now_iso: str,
) -> None:
    for kind, config_json in rows:
        con.execute(
            f"""
            INSERT INTO {table_name}(id, tenant_id, rule_id, {kind_column}, config_json, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (_new_id(), tenant_id, rule_id, kind, config_json, now_iso, now_iso),
        )


def _list_children(
    con: sqlite3.Connection,
    *,
    tenant_id: str,
    rule_id: str,
    table_name: str,
    kind_column: str,
) -> list[AutomationComponent]:
    rows = con.execute(
        f"""
        SELECT id, tenant_id, rule_id, {kind_column} AS component_type, config_json, created_at, updated_at
        FROM {table_name}
        WHERE tenant_id=? AND rule_id=?
        ORDER BY created_at ASC, id ASC
        """,
        (tenant_id, rule_id),
    ).fetchall()
    out: list[AutomationComponent] = []
    for row in rows:
        out.append(
            {
                "id": str(row["id"]),
                "tenant_id": str(row["tenant_id"]),
                "rule_id": str(row["rule_id"]),
                "type": str(row["component_type"]),
                "config": json.loads(str(row["config_json"] or "{}")),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
        )
    return out


def create_rule(
    *,
    tenant_id: str,
    name: str,
    description: str = "",
    is_enabled: bool = True,
    triggers: Sequence[AutomationComponentInput | Mapping[str, Any]] | None = None,
    conditions: Sequence[AutomationComponentInput | Mapping[str, Any]] | None = None,
    actions: Sequence[AutomationComponentInput | Mapping[str, Any]] | None = None,
    db_path: Path | str | None = None,
) -> str:
    tenant = _norm_tenant(tenant_id)
    rule_name = _norm_name(name)
    rule_description = _norm_description(description)
    trigger_rows = _normalize_components(triggers, "trigger_type")
    condition_rows = _normalize_components(conditions, "condition_type")
    action_rows = _normalize_components(actions, "action_type")
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    now_iso = _now_rfc3339()
    rule_id = _new_id()
    con = _connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            f"""
            INSERT INTO {RULE_TABLE}(id, tenant_id, name, description, is_enabled, created_at, updated_at, version)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                rule_id,
                tenant,
                rule_name,
                rule_description,
                1 if is_enabled else 0,
                now_iso,
                now_iso,
                1,
            ),
        )
        _insert_children(
            con,
            table_name=TRIGGER_TABLE,
            kind_column="trigger_type",
            tenant_id=tenant,
            rule_id=rule_id,
            rows=trigger_rows,
            now_iso=now_iso,
        )
        _insert_children(
            con,
            table_name=CONDITION_TABLE,
            kind_column="condition_type",
            tenant_id=tenant,
            rule_id=rule_id,
            rows=condition_rows,
            now_iso=now_iso,
        )
        _insert_children(
            con,
            table_name=ACTION_TABLE,
            kind_column="action_type",
            tenant_id=tenant,
            rule_id=rule_id,
            rows=action_rows,
            now_iso=now_iso,
        )
        con.commit()
    finally:
        con.close()

    _event(
        event_type="automation.rule.created",
        rule_id=rule_id,
        tenant_id=tenant,
        payload={
            "enabled": 1 if is_enabled else 0,
            "trigger_count": len(trigger_rows),
            "condition_count": len(condition_rows),
            "action_count": len(action_rows),
            "version": 1,
        },
    )
    return rule_id


def get_rule(
    *, tenant_id: str, rule_id: str, db_path: Path | str | None = None
) -> AutomationRuleRecord | None:
    tenant = _norm_tenant(tenant_id)
    rid = str(rule_id or "").strip()
    if not rid:
        raise ValueError("validation_error")
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    con = _connect(path)
    try:
        row = con.execute(
            f"""
            SELECT id, tenant_id, name, description, is_enabled, created_at, updated_at, version
            FROM {RULE_TABLE}
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant, rid),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": str(row["name"]),
            "description": str(row["description"] or ""),
            "is_enabled": bool(int(row["is_enabled"] or 0)),
            "version": int(row["version"] or 1),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
            "triggers": _list_children(
                con,
                tenant_id=tenant,
                rule_id=rid,
                table_name=TRIGGER_TABLE,
                kind_column="trigger_type",
            ),
            "conditions": _list_children(
                con,
                tenant_id=tenant,
                rule_id=rid,
                table_name=CONDITION_TABLE,
                kind_column="condition_type",
            ),
            "actions": _list_children(
                con,
                tenant_id=tenant,
                rule_id=rid,
                table_name=ACTION_TABLE,
                kind_column="action_type",
            ),
        }
    finally:
        con.close()


def list_rules(
    *, tenant_id: str, db_path: Path | str | None = None
) -> list[AutomationRuleSummary]:
    tenant = _norm_tenant(tenant_id)
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    con = _connect(path)
    try:
        rows = con.execute(
            f"""
            SELECT
              r.id,
              r.tenant_id,
              r.name,
              r.description,
              r.is_enabled,
              r.version,
              r.created_at,
              r.updated_at,
              (SELECT COUNT(1) FROM {TRIGGER_TABLE} t WHERE t.tenant_id=r.tenant_id AND t.rule_id=r.id) AS trigger_count,
              (SELECT COUNT(1) FROM {CONDITION_TABLE} c WHERE c.tenant_id=r.tenant_id AND c.rule_id=r.id) AS condition_count,
              (SELECT COUNT(1) FROM {ACTION_TABLE} a WHERE a.tenant_id=r.tenant_id AND a.rule_id=r.id) AS action_count
            FROM {RULE_TABLE} r
            WHERE r.tenant_id=?
            ORDER BY r.updated_at DESC, r.id DESC
            """,
            (tenant,),
        ).fetchall()
        out: list[AutomationRuleSummary] = []
        for row in rows:
            out.append(
                {
                    "id": str(row["id"]),
                    "tenant_id": str(row["tenant_id"]),
                    "name": str(row["name"]),
                    "description": str(row["description"] or ""),
                    "is_enabled": bool(int(row["is_enabled"] or 0)),
                    "version": int(row["version"] or 1),
                    "created_at": str(row["created_at"] or ""),
                    "updated_at": str(row["updated_at"] or ""),
                    "trigger_count": int(row["trigger_count"] or 0),
                    "condition_count": int(row["condition_count"] or 0),
                    "action_count": int(row["action_count"] or 0),
                }
            )
        return out
    finally:
        con.close()


def update_rule(
    *,
    tenant_id: str,
    rule_id: str,
    patch: Mapping[str, Any],
    db_path: Path | str | None = None,
) -> AutomationRuleRecord | None:
    tenant = _norm_tenant(tenant_id)
    rid = str(rule_id or "").strip()
    if not rid or not isinstance(patch, Mapping):
        raise ValueError("validation_error")
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    con = _connect(path)
    now_iso = _now_rfc3339()
    try:
        existing = con.execute(
            f"""
            SELECT id, name, description, is_enabled
            FROM {RULE_TABLE}
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant, rid),
        ).fetchone()
        if existing is None:
            return None

        name = (
            _norm_name(str(patch["name"]))
            if "name" in patch
            else str(existing["name"] or "")
        )
        description = (
            _norm_description(str(patch["description"]))
            if "description" in patch
            else str(existing["description"] or "")
        )
        is_enabled = (
            bool(patch["is_enabled"])
            if "is_enabled" in patch
            else bool(int(existing["is_enabled"] or 0))
        )

        trigger_rows = (
            _normalize_components(patch.get("triggers"), "trigger_type")
            if "triggers" in patch
            else None
        )
        condition_rows = (
            _normalize_components(patch.get("conditions"), "condition_type")
            if "conditions" in patch
            else None
        )
        action_rows = (
            _normalize_components(patch.get("actions"), "action_type")
            if "actions" in patch
            else None
        )

        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            f"""
            UPDATE {RULE_TABLE}
            SET name=?, description=?, is_enabled=?, updated_at=?, version=version+1
            WHERE tenant_id=? AND id=?
            """,
            (
                name,
                description,
                1 if is_enabled else 0,
                now_iso,
                tenant,
                rid,
            ),
        )
        if cur.rowcount <= 0:
            con.rollback()
            return None

        if trigger_rows is not None:
            con.execute(
                f"DELETE FROM {TRIGGER_TABLE} WHERE tenant_id=? AND rule_id=?",
                (tenant, rid),
            )
            _insert_children(
                con,
                table_name=TRIGGER_TABLE,
                kind_column="trigger_type",
                tenant_id=tenant,
                rule_id=rid,
                rows=trigger_rows,
                now_iso=now_iso,
            )
        if condition_rows is not None:
            con.execute(
                f"DELETE FROM {CONDITION_TABLE} WHERE tenant_id=? AND rule_id=?",
                (tenant, rid),
            )
            _insert_children(
                con,
                table_name=CONDITION_TABLE,
                kind_column="condition_type",
                tenant_id=tenant,
                rule_id=rid,
                rows=condition_rows,
                now_iso=now_iso,
            )
        if action_rows is not None:
            con.execute(
                f"DELETE FROM {ACTION_TABLE} WHERE tenant_id=? AND rule_id=?",
                (tenant, rid),
            )
            _insert_children(
                con,
                table_name=ACTION_TABLE,
                kind_column="action_type",
                tenant_id=tenant,
                rule_id=rid,
                rows=action_rows,
                now_iso=now_iso,
            )

        con.commit()
    finally:
        con.close()

    updated = get_rule(tenant_id=tenant, rule_id=rid, db_path=path)
    if updated is None:
        return None
    _event(
        event_type="automation.rule.updated",
        rule_id=rid,
        tenant_id=tenant,
        payload={
            "enabled": 1 if updated["is_enabled"] else 0,
            "version": int(updated["version"]),
            "trigger_count": len(updated["triggers"]),
            "condition_count": len(updated["conditions"]),
            "action_count": len(updated["actions"]),
        },
    )
    return updated


def delete_rule(
    *, tenant_id: str, rule_id: str, db_path: Path | str | None = None
) -> bool:
    tenant = _norm_tenant(tenant_id)
    rid = str(rule_id or "").strip()
    if not rid:
        raise ValueError("validation_error")
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    con = _connect(path)
    try:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            f"DELETE FROM {RULE_TABLE} WHERE tenant_id=? AND id=?",
            (tenant, rid),
        )
        deleted = int(cur.rowcount or 0) > 0
        con.commit()
    finally:
        con.close()

    if deleted:
        _event(
            event_type="automation.rule.deleted",
            rule_id=rid,
            tenant_id=tenant,
            payload={"deleted": 1},
        )
    return deleted


def get_state_cursor(
    *, tenant_id: str, source: str, db_path: Path | str | None = None
) -> str:
    tenant = _norm_tenant(tenant_id)
    src = str(source or "").strip()
    if not src:
        raise ValueError("validation_error")
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    con = _connect(path)
    try:
        row = con.execute(
            f"SELECT cursor FROM {STATE_TABLE} WHERE tenant_id=? AND source=? LIMIT 1",
            (tenant, src),
        ).fetchone()
        if row is None:
            return ""
        return str(row["cursor"] or "")
    finally:
        con.close()


def upsert_state_cursor(
    *,
    tenant_id: str,
    source: str,
    cursor: str,
    db_path: Path | str | None = None,
) -> None:
    tenant = _norm_tenant(tenant_id)
    src = str(source or "").strip()
    cur = str(cursor or "").strip()
    if not src or not cur:
        raise ValueError("validation_error")
    ensure_automation_schema(db_path)
    path = _resolve_db_path(db_path)
    con = _connect(path)
    try:
        now_iso = _now_rfc3339()
        con.execute(
            f"""
            INSERT INTO {STATE_TABLE}(id, tenant_id, source, cursor, updated_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(tenant_id, source) DO UPDATE
              SET cursor=excluded.cursor, updated_at=excluded.updated_at
            """,
            (_new_id(), tenant, src, cur, now_iso),
        )
        con.commit()
    finally:
        con.close()
