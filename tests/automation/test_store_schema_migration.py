from __future__ import annotations

import sqlite3

import pytest

from app.modules.automation.store import EXECUTION_LOG_TABLE, ensure_automation_schema


def test_legacy_execution_log_migration_allows_duplicate_empty_trigger_ref(tmp_path):
    db_path = tmp_path / "automation.sqlite3"

    with sqlite3.connect(db_path) as con:
        con.execute(
            f"""
            CREATE TABLE {EXECUTION_LOG_TABLE}(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              trigger_type TEXT NOT NULL,
              status TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT NOT NULL DEFAULT '',
              error_redacted TEXT NOT NULL DEFAULT '',
              output_redacted TEXT NOT NULL DEFAULT ''
            )
            """
        )
        con.execute(
            f"""
            INSERT INTO {EXECUTION_LOG_TABLE}(
              id, tenant_id, rule_id, trigger_type, status, started_at, finished_at, error_redacted, output_redacted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("1", "tenant-a", "rule-a", "event", "ok", "2025-01-01T00:00:00Z", "", "", ""),
        )
        con.execute(
            f"""
            INSERT INTO {EXECUTION_LOG_TABLE}(
              id, tenant_id, rule_id, trigger_type, status, started_at, finished_at, error_redacted, output_redacted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2", "tenant-a", "rule-a", "event", "failed", "2025-01-01T00:01:00Z", "", "", ""),
        )

    ensure_automation_schema(db_path)

    with sqlite3.connect(db_path) as con:
        con.execute(
            f"""
            INSERT INTO {EXECUTION_LOG_TABLE}(
              id, tenant_id, rule_id, trigger_type, trigger_ref, status, started_at, finished_at, error_redacted, output_redacted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("3", "tenant-a", "rule-a", "event", "", "ok", "2025-01-01T00:02:00Z", "", "", ""),
        )
        con.execute(
            f"""
            INSERT INTO {EXECUTION_LOG_TABLE}(
              id, tenant_id, rule_id, trigger_type, trigger_ref, status, started_at, finished_at, error_redacted, output_redacted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("4", "tenant-a", "rule-a", "event", "ref-1", "ok", "2025-01-01T00:03:00Z", "", "", ""),
        )

        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                f"""
                INSERT INTO {EXECUTION_LOG_TABLE}(
                  id, tenant_id, rule_id, trigger_type, trigger_ref, status, started_at, finished_at, error_redacted, output_redacted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("5", "tenant-a", "rule-a", "event", "ref-1", "ok", "2025-01-01T00:04:00Z", "", "", ""),
            )
