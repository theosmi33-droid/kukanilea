from pathlib import Path

import sqlite3

import pytest

from app.core.migrations import run_migrations, validate_integrity
from scripts.seed_demo_data import seed_demo_data


def _column_names(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_run_migrations_is_idempotent(tmp_path):
    db_path = tmp_path / "core.sqlite3"

    run_migrations(db_path)
    run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert user_version == 6
        columns = _column_names(conn, "agent_memory")
        assert "importance_score" in columns
        assert "category" in columns

        idx_names = {
            r[1]
            for r in conn.execute(
                "SELECT type, name FROM sqlite_master WHERE type='index' AND tbl_name='agent_memory'"
            ).fetchall()
        }
        assert "idx_memory_tenant_ts" in idx_names
        validate_integrity(conn)
    finally:
        conn.close()


def test_validate_integrity_detects_missing_agent_memory_index(tmp_path):
    db_path = tmp_path / "core_missing_idx.sqlite3"
    run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP INDEX IF EXISTS idx_memory_tenant_ts")
        conn.commit()

        with pytest.raises(ValueError, match="missing_index:idx_memory_tenant_ts"):
            validate_integrity(conn)
    finally:
        conn.close()


def test_seed_demo_data_upserts_without_duplicates(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    tenant_id = "DEMO_INTEGRITY"

    first = seed_demo_data(db_path, tenant_id)
    second = seed_demo_data(db_path, tenant_id)

    assert first == second
    assert second["projects"] >= 3
    assert second["tasks"] >= 6
    assert second["contacts"] >= 4
    assert second["documents"] >= 3
