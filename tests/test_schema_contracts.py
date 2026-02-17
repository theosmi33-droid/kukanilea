from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.db import AuthDB


def test_core_create_table_statements_are_idempotent() -> None:
    source = Path("kukanilea_core_v3_fixed.py").read_text(encoding="utf-8")
    stmts = re.findall(r"CREATE\s+TABLE\s+[^\n]*", source, flags=re.IGNORECASE)
    assert stmts, "Expected CREATE TABLE statements in core migration file"
    offenders = [s for s in stmts if "IF NOT EXISTS" not in s.upper()]
    assert not offenders, f"Non-idempotent CREATE TABLE found: {offenders[:3]}"


def test_selected_tables_use_text_ids_and_tenant_fields(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.sqlite3"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()

    auth_db = AuthDB(tmp_path / "auth.sqlite3")
    auth_db.init()

    con_core = sqlite3.connect(str(core.DB_PATH))
    con_core.row_factory = sqlite3.Row
    try:
        rows = con_core.execute("PRAGMA table_info(autonomy_ocr_jobs)").fetchall()
        cols = {str(r["name"]): str(r["type"]).upper() for r in rows}
        assert cols.get("id") == "TEXT"
        assert "tenant_id" in cols
    finally:
        con_core.close()

    con_auth = sqlite3.connect(str(tmp_path / "auth.sqlite3"))
    con_auth.row_factory = sqlite3.Row
    try:
        outbox_rows = con_auth.execute("PRAGMA table_info(auth_outbox)").fetchall()
        outbox_cols = {str(r["name"]): str(r["type"]).upper() for r in outbox_rows}
        assert outbox_cols.get("id") == "TEXT"
        assert "tenant_id" in outbox_cols

        chat_rows = con_auth.execute("PRAGMA table_info(chat_history)").fetchall()
        chat_cols = {str(r["name"]): str(r["type"]).upper() for r in chat_rows}
        assert chat_cols.get("id") == "TEXT"
        assert "tenant_id" in chat_cols
    finally:
        con_auth.close()
