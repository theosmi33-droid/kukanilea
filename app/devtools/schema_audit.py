from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Config

DEFAULT_GLOBAL_TABLES = {
    "meta",
    "users",
    "tenants",
    "memberships",
    "auth_outbox",
    "chat_history",
    "license_state",
    "events",
    "benchmarks",
    "ontology_types",
    "review_locks",
    "roles",
    "skills",
    "tenant_config",
}
DEFAULT_GLOBAL_TABLE_PREFIXES = ("docs_fts", "knowledge_fts", "derived_")


@dataclass(frozen=True)
class TableFinding:
    table: str
    code: str
    message: str


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _table_info(con: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return [
        {
            "name": str(r["name"]),
            "type": str(r["type"] or ""),
            "pk": int(r["pk"] or 0),
        }
        for r in rows
    ]


def analyze_db(
    db_path: Path,
    *,
    global_tables: set[str] | None = None,
) -> dict[str, Any]:
    path = Path(db_path)
    result: dict[str, Any] = {
        "db_path": str(path),
        "exists": path.exists(),
        "tables": [],
        "findings": [],
        "ok": True,
    }
    if not path.exists():
        result["ok"] = False
        result["findings"] = [
            {
                "table": "<db>",
                "code": "db_missing",
                "message": "Database file does not exist.",
            }
        ]
        return result

    global_allow = {t.lower() for t in (global_tables or DEFAULT_GLOBAL_TABLES)}

    con = _connect(path)
    try:
        rows = con.execute(
            """
            SELECT name, COALESCE(sql, '') AS sql
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name ASC
            """
        ).fetchall()

        findings: list[TableFinding] = []
        tables_payload: list[dict[str, Any]] = []

        for row in rows:
            table = str(row["name"])
            sql = str(row["sql"] or "")
            columns = _table_info(con, table)

            has_tenant = any(c["name"].lower() == "tenant_id" for c in columns)
            table_lower = table.lower()
            is_global_prefix = any(
                table_lower.startswith(prefix)
                for prefix in DEFAULT_GLOBAL_TABLE_PREFIXES
            )
            requires_tenant = table_lower not in global_allow and not is_global_prefix

            id_col = next((c for c in columns if c["name"].lower() == "id"), None)
            id_pk = bool(id_col and int(id_col["pk"] or 0) > 0)
            id_type = str(id_col["type"] if id_col else "")
            id_type_upper = id_type.upper()
            id_is_text = id_pk and id_type_upper.startswith("TEXT")
            id_is_integer = id_pk and "INT" in id_type_upper
            has_autoincrement = "AUTOINCREMENT" in sql.upper()

            if requires_tenant and not has_tenant:
                findings.append(
                    TableFinding(
                        table=table,
                        code="missing_tenant_id",
                        message="Table is not global and has no tenant_id column.",
                    )
                )

            if id_pk and not id_is_text:
                findings.append(
                    TableFinding(
                        table=table,
                        code="id_not_text_pk",
                        message=f"Primary key 'id' is '{id_type or 'UNKNOWN'}', expected TEXT.",
                    )
                )

            if id_is_integer and has_autoincrement:
                findings.append(
                    TableFinding(
                        table=table,
                        code="autoincrement_pk",
                        message="Table uses INTEGER PRIMARY KEY AUTOINCREMENT.",
                    )
                )

            tables_payload.append(
                {
                    "table": table,
                    "has_tenant_id": has_tenant,
                    "requires_tenant_id": requires_tenant,
                    "id_pk": id_pk,
                    "id_type": id_type,
                    "id_is_text_pk": id_is_text,
                    "id_is_integer_pk": id_is_integer,
                    "autoincrement": has_autoincrement,
                    "columns": columns,
                }
            )

        result["tables"] = tables_payload
        result["findings"] = [f.__dict__ for f in findings]
        result["ok"] = not findings
        result["summary"] = {
            "table_count": len(tables_payload),
            "finding_count": len(findings),
            "autoincrement_tables": sorted(
                {f.table for f in findings if f.code == "autoincrement_pk"}
            ),
            "non_text_id_tables": sorted(
                {f.table for f in findings if f.code == "id_not_text_pk"}
            ),
            "missing_tenant_tables": sorted(
                {f.table for f in findings if f.code == "missing_tenant_id"}
            ),
        }
        return result
    finally:
        con.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit DB schema for TEXT IDs and tenant columns."
    )
    parser.add_argument(
        "--core-db", default=str(Config.CORE_DB), help="Path to core sqlite DB"
    )
    parser.add_argument(
        "--auth-db", default=str(Config.AUTH_DB), help="Path to auth sqlite DB"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with code 1 if schema findings exist.",
    )
    return parser.parse_args()


def _print_human(report: dict[str, Any]) -> None:
    for key in ("core", "auth"):
        section = report[key]
        summary = section.get("summary", {})
        print(
            f"[{key}] ok={section.get('ok')} tables={summary.get('table_count', 0)} findings={summary.get('finding_count', 0)}"
        )
        for finding in section.get("findings", []):
            print(f"  - {finding['table']}: {finding['code']} ({finding['message']})")


def main() -> int:
    args = _parse_args()
    report = {
        "core": analyze_db(Path(args.core_db)),
        "auth": analyze_db(Path(args.auth_db)),
    }
    report["ok"] = bool(report["core"].get("ok") and report["auth"].get("ok"))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        _print_human(report)

    if args.fail_on_findings and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
