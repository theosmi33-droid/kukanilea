from __future__ import annotations

import sqlite3
from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.store import (
    PENDING_ACTION_TABLE,
    RULE_TABLE,
    ensure_automation_schema,
)


def _table_columns(db_path: Path, table_name: str) -> set[str]:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}
    finally:
        con.close()


def _bootstrap_legacy_automation_schema(db_path: Path) -> None:
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS automation_builder_rules(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              is_enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS automation_builder_pending_actions(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              action_type TEXT NOT NULL,
              action_config TEXT NOT NULL,
              context_snapshot TEXT NOT NULL,
              created_at TEXT NOT NULL,
              confirmed_at TEXT
            )
            """
        )
        con.commit()
    finally:
        con.close()


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


def test_upgrade_smoke_automation_schema_and_page(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    _bootstrap_legacy_automation_schema(db_path)

    ensure_automation_schema(db_path)

    rule_columns = _table_columns(db_path, RULE_TABLE)
    assert "max_executions_per_minute" in rule_columns

    pending_columns = _table_columns(db_path, PENDING_ACTION_TABLE)
    assert "status" in pending_columns
    assert "confirm_token" in pending_columns

    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        index_rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (PENDING_ACTION_TABLE,),
        ).fetchall()
        index_names = {str(row["name"]) for row in index_rows}
        assert (
            "idx_automation_builder_pending_actions_tenant_confirm_token" in index_names
        )
    finally:
        con.close()

    webmod.core.DB_PATH = db_path
    core.DB_PATH = db_path

    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)
    page = client.get("/automation")
    assert page.status_code == 200
    assert b"Automation Builder" in page.data
