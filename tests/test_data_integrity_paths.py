from pathlib import Path

from app.core.migrations import run_migrations
from scripts.seed_demo_data import seed_demo_data


def _column_names(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_run_migrations_is_idempotent(tmp_path):
    db_path = tmp_path / "core.sqlite3"

    run_migrations(db_path)
    run_migrations(db_path)

    import sqlite3

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
