from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_OCR_COLUMNS = {"allow_ocr", "ocr_enabled", "ocr_allowed"}
PATH_COLUMNS = {"documents_inbox_dir", "inbox_dir", "watch_dir", "path"}

_DEFAULT_INSERT_VALUES = {
    "allow_manual": 1,
    "allow_tasks": 1,
    "allow_projects": 1,
    "allow_documents": 0,
    "allow_leads": 0,
    "allow_email": 0,
    "allow_calendar": 0,
    "allow_customer_pii": 0,
}
_DEFAULT_WATCH_INSERT_VALUES = {
    "enabled": 1,
    "max_bytes_per_file": 262_144,
    "max_files_per_scan": 200,
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _table_info(con: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "cid": int(row[0]),
                "name": str(row[1]),
                "type": str(row[2] or ""),
                "notnull": int(row[3] or 0),
                "dflt_value": row[4],
                "pk": int(row[5] or 0),
            }
        )
    return out


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def get_policy_status(tenant_id: str, *, db_path: Path) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip() or "default"
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        columns_meta = _table_info(con, "knowledge_source_policies")
        existing_columns = [str(c["name"]) for c in columns_meta]
        if not existing_columns:
            return {
                "ok": False,
                "reason": "schema_unknown",
                "table": "knowledge_source_policies",
                "existing_columns": [],
            }
        candidates = sorted(c for c in existing_columns if c in ALLOWED_OCR_COLUMNS)
        if not candidates:
            return {
                "ok": False,
                "reason": "schema_unknown",
                "table": "knowledge_source_policies",
                "existing_columns": existing_columns,
            }
        if len(candidates) > 1:
            return {
                "ok": False,
                "reason": "ambiguous_columns",
                "candidates": candidates,
                "existing_columns": existing_columns,
                "table": "knowledge_source_policies",
            }
        ocr_col = candidates[0]
        row = con.execute(
            f"""
            SELECT tenant_id, "{ocr_col}" AS ocr_flag
            FROM knowledge_source_policies
            WHERE tenant_id=?
            LIMIT 1
            """,
            (tenant,),
        ).fetchone()
        row_present = bool(row)
        policy_enabled = bool(int((row["ocr_flag"] if row else 0) or 0))
        return {
            "ok": True,
            "policy_enabled": policy_enabled,
            "ocr_column": ocr_col,
            "row_present": row_present,
            "existing_columns": existing_columns,
            "table": "knowledge_source_policies",
        }
    finally:
        con.close()


def enable_ocr_policy_in_db(
    tenant_id: str,
    *,
    db_path: Path,
    confirm: bool,
    read_only: bool,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip() or "default"
    if read_only:
        return {
            "ok": False,
            "reason": "read_only",
            "tenant_id": tenant,
        }
    if not confirm:
        return {
            "ok": False,
            "reason": "confirm_required",
            "tenant_id": tenant,
        }

    status = get_policy_status(tenant, db_path=db_path)
    if not status.get("ok"):
        return {
            "ok": False,
            "reason": str(status.get("reason") or "schema_unknown"),
            "tenant_id": tenant,
            "existing_columns": list(status.get("existing_columns") or []),
            "candidates": list(status.get("candidates") or []),
            "table": "knowledge_source_policies",
        }

    ocr_col = str(status["ocr_column"])
    row_present = bool(status["row_present"])
    existing_columns = list(status.get("existing_columns") or [])

    con = sqlite3.connect(str(db_path))
    try:
        if row_present:
            con.execute(
                f"""
                UPDATE knowledge_source_policies
                SET "{ocr_col}"=1
                WHERE tenant_id=?
                """,
                (tenant,),
            )
            con.commit()
            return {
                "ok": True,
                "tenant_id": tenant,
                "ocr_column": ocr_col,
                "changed": not bool(status.get("policy_enabled")),
                "row_present": True,
                "existing_columns": existing_columns,
            }

        columns_meta = _table_info(con, "knowledge_source_policies")
        values: dict[str, Any] = {"tenant_id": tenant, ocr_col: 1}
        for col in columns_meta:
            name = str(col["name"])
            if name in values:
                continue
            if name in _DEFAULT_INSERT_VALUES:
                values[name] = _DEFAULT_INSERT_VALUES[name]
                continue
            if name == "updated_at":
                values[name] = _now_iso()
                continue
            not_null = int(col.get("notnull") or 0) == 1
            has_default = col.get("dflt_value") is not None
            if not_null and not has_default:
                return {
                    "ok": False,
                    "reason": "schema_unknown_insert",
                    "tenant_id": tenant,
                    "existing_columns": existing_columns,
                    "unknown_required_columns": [name],
                    "table": "knowledge_source_policies",
                }

        cols = sorted(values.keys())
        placeholders = ", ".join("?" for _ in cols)
        columns_sql = ", ".join(f'"{c}"' for c in cols)
        params = [values[c] for c in cols]
        con.execute(
            f"""
            INSERT INTO knowledge_source_policies({columns_sql})
            VALUES ({placeholders})
            """,
            tuple(params),
        )
        con.commit()
        return {
            "ok": True,
            "tenant_id": tenant,
            "ocr_column": ocr_col,
            "changed": True,
            "row_present": False,
            "existing_columns": existing_columns,
        }
    finally:
        con.close()


def ensure_watch_config_in_sandbox(
    tenant_id: str,
    *,
    sandbox_db_path: Path,
    inbox_dir: str,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip() or "default"
    inbox_value = (
        str(inbox_dir or "")
        .replace("\x00", "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
    )
    con = sqlite3.connect(str(sandbox_db_path))
    con.row_factory = sqlite3.Row
    try:
        if not _table_exists(con, "source_watch_config"):
            return {
                "ok": False,
                "reason": "watch_config_table_missing",
                "table": "source_watch_config",
            }

        columns_meta = _table_info(con, "source_watch_config")
        existing_columns = [str(c["name"]) for c in columns_meta]
        candidates = [
            c
            for c in ("documents_inbox_dir", "inbox_dir", "watch_dir", "path")
            if c in existing_columns
        ]
        if not candidates:
            return {
                "ok": False,
                "reason": "schema_unknown",
                "table": "source_watch_config",
                "existing_columns": existing_columns,
            }
        path_col = candidates[0]

        row = con.execute(
            "SELECT tenant_id FROM source_watch_config WHERE tenant_id=? LIMIT 1",
            (tenant,),
        ).fetchone()
        existed_before = row is not None

        if existed_before:
            assignments = [f'"{path_col}"=?']
            params: list[Any] = [inbox_value]
            if "enabled" in existing_columns:
                assignments.append('"enabled"=?')
                params.append(1)
            if "updated_at" in existing_columns:
                assignments.append('"updated_at"=?')
                params.append(_now_iso())
            params.append(tenant)
            con.execute(
                f"""
                UPDATE source_watch_config
                SET {", ".join(assignments)}
                WHERE tenant_id=?
                """,
                tuple(params),
            )
            con.commit()
            return {
                "ok": True,
                "seeded": False,
                "existed_before": True,
                "inbox_dir": inbox_value,
                "used_column": path_col,
                "existing_columns": existing_columns,
            }

        values: dict[str, Any] = {
            "tenant_id": tenant,
            path_col: inbox_value,
        }
        for col in columns_meta:
            name = str(col["name"])
            if name in values:
                continue
            if name in _DEFAULT_WATCH_INSERT_VALUES:
                values[name] = _DEFAULT_WATCH_INSERT_VALUES[name]
                continue
            if name == "updated_at":
                values[name] = _now_iso()
                continue
            not_null = int(col.get("notnull") or 0) == 1
            has_default = col.get("dflt_value") is not None
            if not_null and not has_default:
                return {
                    "ok": False,
                    "reason": "schema_unknown_insert",
                    "table": "source_watch_config",
                    "existing_columns": existing_columns,
                    "unknown_required_columns": [name],
                }

        cols = sorted(values.keys())
        placeholders = ", ".join("?" for _ in cols)
        columns_sql = ", ".join(f'"{c}"' for c in cols)
        params = [values[c] for c in cols]
        con.execute(
            f"""
            INSERT INTO source_watch_config({columns_sql})
            VALUES ({placeholders})
            """,
            tuple(params),
        )
        con.commit()
        return {
            "ok": True,
            "seeded": True,
            "existed_before": False,
            "inbox_dir": inbox_value,
            "used_column": path_col,
            "existing_columns": existing_columns,
        }
    finally:
        con.close()
