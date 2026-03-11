from __future__ import annotations

import sqlite3

from app.core.migrations import run_migrations
from app.modules.automation.store import (
    append_execution_log,
    create_rule,
    ensure_automation_schema,
)


def test_schema_upgrade_tolerates_legacy_execution_rows_without_trigger_ref(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DROP TABLE IF EXISTS automation_builder_execution_log")
        con.execute(
            """
            CREATE TABLE automation_builder_execution_log(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              trigger_type TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            "INSERT INTO automation_builder_execution_log(id, tenant_id, rule_id, trigger_type, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("1", "T", "R", "event", "ok", "2025-01-01T00:00:00Z"),
        )
        con.execute(
            "INSERT INTO automation_builder_execution_log(id, tenant_id, rule_id, trigger_type, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2", "T", "R", "event", "ok", "2025-01-01T00:00:01Z"),
        )
        con.commit()
    finally:
        con.close()

    run_migrations(db_path)
    ensure_automation_schema(db_path)

    with sqlite3.connect(str(db_path)) as verify_con:
        idx_row = verify_con.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_automation_builder_execution_log_unique'"
        ).fetchone()
        assert idx_row is not None
        assert "WHERE trigger_ref <> ''" in str(idx_row[0] or "")


def test_ensure_schema_tolerates_legacy_execution_rows_without_core_migrations(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DROP TABLE IF EXISTS automation_builder_execution_log")
        con.execute(
            """
            CREATE TABLE automation_builder_execution_log(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              trigger_type TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            "INSERT INTO automation_builder_execution_log(id, tenant_id, rule_id, trigger_type, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("1", "T", "R", "event", "ok", "2025-01-01T00:00:00Z"),
        )
        con.execute(
            "INSERT INTO automation_builder_execution_log(id, tenant_id, rule_id, trigger_type, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2", "T", "R", "event", "ok", "2025-01-01T00:00:01Z"),
        )
        con.commit()
    finally:
        con.close()

    ensure_automation_schema(db_path)

    with sqlite3.connect(str(db_path)) as verify_con:
        idx_row = verify_con.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_automation_builder_execution_log_unique'"
        ).fetchone()
        assert idx_row is not None
        assert "WHERE trigger_ref <> ''" in str(idx_row[0] or "")


def test_execution_log_unique_index_still_deduplicates_non_empty_trigger_ref(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    ensure_automation_schema(db_path)
    rule_id = create_rule(tenant_id="KUKANILEA", name="rule-1", db_path=db_path)

    first = append_execution_log(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        trigger_type="event",
        trigger_ref="evt-1",
        status="started",
        db_path=db_path,
    )
    second = append_execution_log(
        tenant_id="KUKANILEA",
        rule_id=rule_id,
        trigger_type="event",
        trigger_ref="evt-1",
        status="started",
        db_path=db_path,
    )

    assert first["ok"] is True
    assert first["duplicate"] is False
    assert second["ok"] is True
    assert second["duplicate"] is True
