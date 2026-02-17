from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.automation.store import (
    ACTION_TABLE,
    CONDITION_TABLE,
    EXECUTION_LOG_TABLE,
    RULE_TABLE,
    STATE_TABLE,
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
            STATE_TABLE,
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
        assert f"idx_{EXECUTION_LOG_TABLE}_unique" in index_names
        assert f"idx_{STATE_TABLE}_tenant_source" in index_names
    finally:
        con.close()


def test_automation_schema_state_unique_and_execution_trigger_ref_unique(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "core.sqlite3"
    ensure_automation_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute(
            f"""
            INSERT INTO {RULE_TABLE}(id, tenant_id, name, description, is_enabled, created_at, updated_at, version)
            VALUES ('rule-1','TENANT_A','Rule','',1,'2026-02-17T00:00:00Z','2026-02-17T00:00:00Z',1)
            """
        )
        con.execute(
            f"""
            INSERT INTO {STATE_TABLE}(id, tenant_id, source, cursor, updated_at)
            VALUES ('state-1','TENANT_A','eventlog','10','2026-02-17T00:00:00Z')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"""
                INSERT INTO {STATE_TABLE}(id, tenant_id, source, cursor, updated_at)
                VALUES ('state-2','TENANT_A','eventlog','11','2026-02-17T00:00:01Z')
                """
            )

        con.execute(
            f"""
            INSERT INTO {EXECUTION_LOG_TABLE}(
              id, tenant_id, rule_id, trigger_type, trigger_ref, status, started_at, finished_at, error_redacted, output_redacted
            ) VALUES ('log-1','TENANT_A','rule-1','eventlog','event:100','started','2026-02-17T00:00:00Z','','','')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"""
                INSERT INTO {EXECUTION_LOG_TABLE}(
                  id, tenant_id, rule_id, trigger_type, trigger_ref, status, started_at, finished_at, error_redacted, output_redacted
                ) VALUES ('log-2','TENANT_A','rule-1','eventlog','event:100','started','2026-02-17T00:00:01Z','','','')
                """
            )
    finally:
        con.close()


def test_automation_schema_foreign_keys_enforced(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    ensure_automation_schema(db_path)
    con = _connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"""
                INSERT INTO {TRIGGER_TABLE}(id, tenant_id, rule_id, trigger_type, config_json, created_at, updated_at)
                VALUES ('trg-1','TENANT_A','missing-rule','eventlog','{{}}','2026-02-17T00:00:00Z','2026-02-17T00:00:00Z')
                """
            )
    finally:
        con.close()
