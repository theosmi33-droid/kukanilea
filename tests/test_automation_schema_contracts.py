from __future__ import annotations

import sqlite3
from pathlib import Path

from app.automation.store import (
    ACTION_TABLE,
    CONDITION_TABLE,
    EXECUTION_LOG_TABLE,
    RULE_TABLE,
    TRIGGER_TABLE,
    ensure_automation_schema,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _table_columns(con: sqlite3.Connection, table_name: str) -> dict[str, sqlite3.Row]:
    rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(r["name"]): r for r in rows}


def test_automation_schema_contracts_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    ensure_automation_schema(db_path)
    ensure_automation_schema(db_path)

    con = _connect(db_path)
    try:
        table_names = {
            str(r["name"])
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            RULE_TABLE,
            TRIGGER_TABLE,
            CONDITION_TABLE,
            ACTION_TABLE,
            EXECUTION_LOG_TABLE,
        }.issubset(table_names)

        rule_cols = _table_columns(con, RULE_TABLE)
        assert "id" in rule_cols and str(rule_cols["id"]["type"]).upper() == "TEXT"
        assert "tenant_id" in rule_cols
        assert "version" in rule_cols

        for table_name in (
            TRIGGER_TABLE,
            CONDITION_TABLE,
            ACTION_TABLE,
            EXECUTION_LOG_TABLE,
        ):
            cols = _table_columns(con, table_name)
            assert "id" in cols and str(cols["id"]["type"]).upper() == "TEXT"
            assert "tenant_id" in cols
            assert "rule_id" in cols

        fk_parents = {
            str(r["table"])
            for r in con.execute(f"PRAGMA foreign_key_list({TRIGGER_TABLE})").fetchall()
        }
        assert RULE_TABLE in fk_parents

        index_names = {
            str(r["name"])
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert f"idx_{RULE_TABLE}_tenant_enabled" in index_names
        assert f"idx_{TRIGGER_TABLE}_tenant_rule" in index_names
        assert f"idx_{CONDITION_TABLE}_tenant_rule" in index_names
        assert f"idx_{ACTION_TABLE}_tenant_rule" in index_names
        assert f"idx_{EXECUTION_LOG_TABLE}_tenant_rule_started" in index_names
    finally:
        con.close()
