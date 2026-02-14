from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import knowledge_policy_get


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_knowledge_tables_exist_and_default_policy_created(tmp_path: Path) -> None:
    _init_core(tmp_path)
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            ).fetchall()
        }
        assert "knowledge_chunks" in tables
        assert "knowledge_source_policies" in tables
        fts_exists = (
            con.execute(
                "SELECT 1 FROM sqlite_master WHERE name='knowledge_fts' LIMIT 1"
            ).fetchone()
            is not None
        )
        fallback_exists = (
            con.execute(
                "SELECT 1 FROM sqlite_master WHERE name='knowledge_fts_fallback' LIMIT 1"
            ).fetchone()
            is not None
        )
        assert fts_exists or fallback_exists
    finally:
        con.close()

    policy = knowledge_policy_get("TENANT_A")
    assert policy["tenant_id"] == "TENANT_A"
    assert int(policy["allow_manual"]) == 1
    assert int(policy["allow_email"]) == 0
