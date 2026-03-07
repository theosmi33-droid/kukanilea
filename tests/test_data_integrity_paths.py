from pathlib import Path

from app.core.migrations import CURRENT_SCHEMA_VERSION, run_migrations
from scripts.seed_demo_data import seed_demo_data


def _column_names(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def test_run_migrations_is_idempotent(tmp_path):
    db_path = tmp_path / "core.sqlite3"

    run_migrations(db_path)
    run_migrations(db_path)

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert user_version == CURRENT_SCHEMA_VERSION
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


def test_run_migrations_repairs_missing_table_even_at_current_version(tmp_path):
    import sqlite3

    db_path = tmp_path / "core.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()

    run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        assert _table_exists(conn, "agent_memory")
        assert _table_exists(conn, "api_outbound_queue")
        assert _table_exists(conn, "memory_audit_log")
    finally:
        conn.close()


def test_run_migrations_keeps_existing_tables_without_error(tmp_path):
    import sqlite3

    db_path = tmp_path / "core.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE agent_memory(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              agent_role TEXT NOT NULL,
              content TEXT NOT NULL,
              embedding BLOB NOT NULL,
              metadata TEXT
            );
            """
        )
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()

    run_migrations(db_path)

    conn = sqlite3.connect(db_path)
    try:
        cols = _column_names(conn, "agent_memory")
        assert "importance_score" in cols
        assert "category" in cols
    finally:
        conn.close()
