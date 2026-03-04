#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

TABLES = ["contacts", "tasks", "projects", "time_entries", "files"]


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    return [str(r[1]) for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def _sample_rows(con: sqlite3.Connection, table: str, tenant_id: str, limit: int = 5) -> List[sqlite3.Row]:
    cols = _table_columns(con, table)
    if "tenant_id" in cols:
        return list(con.execute(f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY rowid ASC LIMIT ?", (tenant_id, limit)))
    if table == "tasks":
        return list(
            con.execute(
                """
                SELECT t.*
                FROM tasks t
                JOIN boards b ON b.id=t.board_id
                JOIN projects p ON p.id=b.project_id
                WHERE p.tenant_id=?
                ORDER BY t.rowid ASC LIMIT ?
                """,
                (tenant_id, limit),
            )
        )
    return []


def _business_entity_stub(table: str, row: sqlite3.Row) -> Dict[str, Any]:
    payload = {k: row[k] for k in row.keys()}
    keys = ["id", "tenant_id", "name", "title", "email", "status", "project_id", "task_id"]
    return {"table": table, **{k: payload.get(k) for k in keys if k in payload}}


def _stable_hash(rows: Iterable[sqlite3.Row]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        payload = {k: row[k] for k in row.keys()}
        digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()


def collect_snapshot(db_path: Path, tenant_id: str) -> Dict[str, Dict[str, Any]]:
    con = _connect(db_path)
    try:
        out: Dict[str, Dict[str, Any]] = {}
        all_entities: List[Dict[str, Any]] = []
        for table in TABLES:
            if not _table_exists(con, table):
                out[table] = {"exists": False, "count": 0, "sample_hash": "missing", "sample_entities": []}
                continue
            cols = _table_columns(con, table)
            if "tenant_id" in cols:
                count = con.execute(f"SELECT COUNT(*) as c FROM {table} WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
            elif table == "tasks":
                count = con.execute(
                    """
                    SELECT COUNT(*)
                    FROM tasks t
                    JOIN boards b ON b.id=t.board_id
                    JOIN projects p ON p.id=b.project_id
                    WHERE p.tenant_id=?
                    """,
                    (tenant_id,),
                ).fetchone()[0]
            else:
                count = 0
            rows = _sample_rows(con, table, tenant_id)
            sample_entities = [_business_entity_stub(table, row) for row in rows]
            all_entities.extend(sample_entities)
            out[table] = {
                "exists": True,
                "count": int(count),
                "sample_hash": _stable_hash(rows),
                "sample_entities": sample_entities,
            }
        out["_business_entities_checksum"] = {
            "sample_count": len(all_entities),
            "checksum": hashlib.sha256(json.dumps(all_entities, sort_keys=True).encode("utf-8")).hexdigest(),
        }
        return out
    finally:
        con.close()


def compare_snapshots(before: Dict[str, Dict[str, Any]], after: Dict[str, Dict[str, Any]]) -> Tuple[bool, List[str]]:
    ok = True
    issues: List[str] = []
    for table in TABLES:
        b = before.get(table, {})
        a = after.get(table, {})
        if b.get("count") != a.get("count"):
            ok = False
            issues.append(f"{table}: count mismatch {b.get('count')} != {a.get('count')}")
        if b.get("sample_hash") != a.get("sample_hash"):
            ok = False
            issues.append(f"{table}: sample_hash mismatch")
    before_checksum = before.get("_business_entities_checksum", {}).get("checksum")
    after_checksum = after.get("_business_entities_checksum", {}).get("checksum")
    if before_checksum != after_checksum:
        ok = False
        issues.append("business_entities_checksum mismatch")
    return ok, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore drill validator (before/after counts + hash samples)")
    parser.add_argument("--db", default="instance/auth.sqlite3", help="SQLite DB path")
    parser.add_argument("--tenant", default="DEMO_TENANT", help="Tenant id")
    parser.add_argument("--baseline", default="instance/restore_baseline.json", help="Baseline file path")
    parser.add_argument("--phase", choices=["before", "after"], default="after")
    args = parser.parse_args()

    db_path = Path(args.db)
    baseline_path = Path(args.baseline)
    snapshot = collect_snapshot(db_path, args.tenant)

    if args.phase == "before":
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"ok": True, "phase": "before", "baseline": str(baseline_path), "snapshot": snapshot}, indent=2))
        return 0

    if not baseline_path.exists():
        print(json.dumps({"ok": False, "error": "missing_baseline", "baseline": str(baseline_path)}, indent=2))
        return 2

    before = json.loads(baseline_path.read_text(encoding="utf-8"))
    ok, issues = compare_snapshots(before, snapshot)
    print(json.dumps({"ok": ok, "phase": "after", "issues": issues, "snapshot": snapshot}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
