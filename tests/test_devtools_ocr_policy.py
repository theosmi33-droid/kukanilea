from __future__ import annotations

import sqlite3
from pathlib import Path

from app.devtools.ocr_policy import (
    enable_ocr_policy_in_db,
    ensure_watch_config_in_sandbox,
    get_policy_status,
)
from app.devtools.sandbox import (
    cleanup_sandbox,
    create_sandbox_copy,
    create_temp_inbox_dir,
    ensure_dir,
    file_sha256,
)


def _create_policy_table(db_path: Path, ddl: str) -> None:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(ddl)
        con.commit()
    finally:
        con.close()


def test_get_policy_status_single_allowed_column(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _create_policy_table(
        db_path,
        """
        CREATE TABLE knowledge_source_policies(
          tenant_id TEXT PRIMARY KEY,
          allow_ocr INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        """,
    )
    con = sqlite3.connect(str(db_path))
    con.execute(
        "INSERT INTO knowledge_source_policies(tenant_id, allow_ocr, updated_at) VALUES (?,?,?)",
        ("dev", 1, "2026-02-16T00:00:00+00:00"),
    )
    con.commit()
    con.close()

    status = get_policy_status("dev", db_path=db_path)
    assert status["ok"] is True
    assert status["policy_enabled"] is True
    assert status["ocr_column"] == "allow_ocr"


def test_get_policy_status_schema_unknown(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _create_policy_table(
        db_path,
        """
        CREATE TABLE knowledge_source_policies(
          tenant_id TEXT PRIMARY KEY,
          allow_documents INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        """,
    )

    status = get_policy_status("dev", db_path=db_path)
    assert status["ok"] is False
    assert status["reason"] == "schema_unknown"
    assert "allow_documents" in status["existing_columns"]


def test_get_policy_status_ambiguous_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _create_policy_table(
        db_path,
        """
        CREATE TABLE knowledge_source_policies(
          tenant_id TEXT PRIMARY KEY,
          allow_ocr INTEGER NOT NULL DEFAULT 0,
          ocr_enabled INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        """,
    )

    status = get_policy_status("dev", db_path=db_path)
    assert status["ok"] is False
    assert status["reason"] == "ambiguous_columns"
    assert set(status["candidates"]) == {"allow_ocr", "ocr_enabled"}


def test_enable_ocr_policy_in_db_read_only_refused(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _create_policy_table(
        db_path,
        """
        CREATE TABLE knowledge_source_policies(
          tenant_id TEXT PRIMARY KEY,
          allow_ocr INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        """,
    )
    result = enable_ocr_policy_in_db(
        "dev",
        db_path=db_path,
        confirm=True,
        read_only=True,
    )
    assert result["ok"] is False
    assert result["reason"] == "read_only"


def test_enable_in_sandbox_does_not_mutate_base_db(tmp_path: Path, monkeypatch) -> None:
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    _create_policy_table(
        base_db,
        """
        CREATE TABLE knowledge_source_policies(
          tenant_id TEXT PRIMARY KEY,
          allow_ocr INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        """,
    )
    con = sqlite3.connect(str(base_db))
    con.execute(
        "INSERT INTO knowledge_source_policies(tenant_id, allow_ocr, updated_at) VALUES (?,?,?)",
        ("dev", 0, "2026-02-16T00:00:00+00:00"),
    )
    con.commit()
    con.close()

    before_hash = file_sha256(base_db)
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    sandbox_db, sandbox_dir = create_sandbox_copy("dev")
    try:
        result = enable_ocr_policy_in_db(
            "dev",
            db_path=sandbox_db,
            confirm=True,
            read_only=False,
        )
        assert result["ok"] is True
    finally:
        cleanup_sandbox(sandbox_dir)

    after_hash = file_sha256(base_db)
    assert before_hash == after_hash

    con2 = sqlite3.connect(str(base_db))
    row = con2.execute(
        "SELECT allow_ocr FROM knowledge_source_policies WHERE tenant_id=?",
        ("dev",),
    ).fetchone()
    con2.close()
    assert int(row[0]) == 0


def test_ensure_watch_config_in_sandbox_updates_existing_row(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _create_policy_table(
        db_path,
        """
        CREATE TABLE source_watch_config(
          tenant_id TEXT PRIMARY KEY,
          documents_inbox_dir TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          max_bytes_per_file INTEGER NOT NULL DEFAULT 262144,
          max_files_per_scan INTEGER NOT NULL DEFAULT 200,
          updated_at TEXT NOT NULL
        );
        """,
    )
    con = sqlite3.connect(str(db_path))
    con.execute(
        """
        INSERT INTO source_watch_config(
          tenant_id, documents_inbox_dir, enabled, max_bytes_per_file, max_files_per_scan, updated_at
        ) VALUES (?,?,?,?,?,?)
        """,
        ("dev", "/tmp/old", 1, 262144, 200, "2026-02-16T00:00:00+00:00"),
    )
    con.commit()
    con.close()

    inbox = str(tmp_path / "inbox")
    result = ensure_watch_config_in_sandbox(
        "dev",
        sandbox_db_path=db_path,
        inbox_dir=inbox,
    )
    assert result["ok"] is True
    assert result["seeded"] is False
    assert result["used_column"] == "documents_inbox_dir"

    con2 = sqlite3.connect(str(db_path))
    row = con2.execute(
        "SELECT documents_inbox_dir FROM source_watch_config WHERE tenant_id=?",
        ("dev",),
    ).fetchone()
    con2.close()
    assert str(row[0]) == inbox


def test_ensure_watch_config_in_sandbox_missing_table(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    sqlite3.connect(str(db_path)).close()
    result = ensure_watch_config_in_sandbox(
        "dev",
        sandbox_db_path=db_path,
        inbox_dir=str(tmp_path / "inbox"),
    )
    assert result["ok"] is False
    assert result["reason"] == "watch_config_table_missing"


def test_ensure_watch_config_in_sandbox_unknown_path_column(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _create_policy_table(
        db_path,
        """
        CREATE TABLE source_watch_config(
          tenant_id TEXT PRIMARY KEY,
          some_other_dir TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL
        );
        """,
    )
    result = ensure_watch_config_in_sandbox(
        "dev",
        sandbox_db_path=db_path,
        inbox_dir=str(tmp_path / "inbox"),
    )
    assert result["ok"] is False
    assert result["reason"] == "schema_unknown"
    assert "some_other_dir" in result["existing_columns"]


def test_sandbox_temp_inbox_helpers(tmp_path: Path) -> None:
    inbox = create_temp_inbox_dir(tmp_path)
    assert inbox.exists()
    assert inbox.is_dir()
    ensured = ensure_dir(inbox)
    assert ensured == inbox
