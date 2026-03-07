import sqlite3
from pathlib import Path

from app import create_app
from app.core.migrations import CURRENT_SCHEMA_VERSION


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _configure_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    auth_db = tmp_path / "auth.sqlite3"
    core_db = tmp_path / "core.sqlite3"
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(core_db))
    monkeypatch.setenv("KUKANILEA_DISABLE_DAEMONS", "1")
    monkeypatch.setenv("KUKANILEA_ENV", "test")
    return auth_db, core_db


def test_bootstrap_fresh_start_creates_expected_migration_tables(monkeypatch, tmp_path):
    _, core_db = _configure_paths(monkeypatch, tmp_path)

    app = create_app()
    assert app is not None

    conn = sqlite3.connect(core_db)
    try:
        assert _table_exists(conn, "agent_memory")
        assert _table_exists(conn, "api_outbound_queue")
        assert _table_exists(conn, "memory_audit_log")
        assert conn.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
    finally:
        conn.close()


def test_bootstrap_repeated_start_is_safe(monkeypatch, tmp_path):
    _, core_db = _configure_paths(monkeypatch, tmp_path)

    app_one = create_app()
    app_two = create_app()

    assert app_one is not None
    assert app_two is not None

    conn = sqlite3.connect(core_db)
    try:
        assert _table_exists(conn, "agent_memory")
        assert _table_exists(conn, "api_outbound_queue")
    finally:
        conn.close()


def test_bootstrap_recovers_missing_migration_table(monkeypatch, tmp_path):
    _, core_db = _configure_paths(monkeypatch, tmp_path)

    conn = sqlite3.connect(core_db)
    try:
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()

    create_app()

    conn = sqlite3.connect(core_db)
    try:
        assert _table_exists(conn, "agent_memory")
        assert _table_exists(conn, "memory_audit_log")
    finally:
        conn.close()


def test_bootstrap_accepts_existing_table_without_error(monkeypatch, tmp_path):
    _, core_db = _configure_paths(monkeypatch, tmp_path)

    conn = sqlite3.connect(core_db)
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

    app = create_app()
    assert app is not None

    conn = sqlite3.connect(core_db)
    try:
        cols = _column_names(conn, "agent_memory")
        assert "importance_score" in cols
        assert "category" in cols
    finally:
        conn.close()
