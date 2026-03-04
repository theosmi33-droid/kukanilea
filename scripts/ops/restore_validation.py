#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict


def _table_count(db: Path, table: str) -> int:
    if not db.exists():
        return 0
    with sqlite3.connect(db) as con:
        try:
            row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error:
            return 0


def collect_metrics(auth_db: Path, core_db: Path) -> Dict[str, int]:
    return {
        "auth.tenants": _table_count(auth_db, "tenants"),
        "auth.memberships": _table_count(auth_db, "memberships"),
        "auth.projects": _table_count(auth_db, "projects"),
        "auth.tasks": _table_count(auth_db, "tasks"),
        "auth.files": _table_count(auth_db, "files"),
        "core.customers": _table_count(core_db, "customers"),
        "core.time_projects": _table_count(core_db, "time_projects"),
        "core.time_entries": _table_count(core_db, "time_entries"),
        "core.docs": _table_count(core_db, "docs"),
        "core.versions": _table_count(core_db, "versions"),
    }


def cmd_snapshot(args: argparse.Namespace) -> int:
    metrics = collect_metrics(args.auth_db, args.core_db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(args.output), "metrics": metrics}, indent=2))
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = collect_metrics(args.auth_db, args.core_db)
    diffs = {k: {"before": before.get(k), "after": v} for k, v in after.items() if before.get(k) != v}
    ok = len(diffs) == 0
    print(json.dumps({"ok": ok, "diffs": diffs, "after": after}, indent=2))
    return 0 if ok else 2


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    default_data_root = Path((root / "instance").as_posix())
    p = argparse.ArgumentParser(description="Validate backup/restore core metrics")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("snapshot")
    s.add_argument("--auth-db", type=Path, default=Path(f"{default_data_root}/auth.sqlite3"))
    s.add_argument("--core-db", type=Path, default=Path(f"{default_data_root}/core.sqlite3"))
    s.add_argument("--output", type=Path, required=True)
    s.set_defaults(func=cmd_snapshot)

    c = sub.add_parser("compare")
    c.add_argument("--before", type=Path, default=root / "evidence/ops/last_restored_metrics.json")
    c.add_argument("--auth-db", type=Path, default=Path(f"{default_data_root}/auth.sqlite3"))
    c.add_argument("--core-db", type=Path, default=Path(f"{default_data_root}/core.sqlite3"))
    c.set_defaults(func=cmd_compare)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        args = parser.parse_args(["compare"])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
