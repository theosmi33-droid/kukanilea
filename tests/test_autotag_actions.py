from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.autotag import autotag_apply_for_source_file, autotag_rule_create
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_autotag_actions_apply_tokens_and_are_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_documents=True,
    )
    autotag_rule_create(
        "TENANT_A",
        name="Invoice Rule",
        priority=5,
        condition_obj={"type": "filename_glob", "pattern": "*rechnung*"},
        action_list=[
            {"type": "add_tag", "tag_name": "rechnung"},
            {"type": "set_doctype", "token": "invoice"},
            {"type": "set_correspondent", "token": "supplier-42"},
        ],
        actor_user_id="dev",
    )

    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "Rechnung_2026-02-15_KD-1234.txt").write_text("A", encoding="utf-8")
    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)
    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        sf = con.execute(
            """
            SELECT id, knowledge_chunk_id, doctype_token, correspondent_token, autotag_applied_at
            FROM source_files
            WHERE tenant_id='TENANT_A'
            LIMIT 1
            """
        ).fetchone()
        assert sf is not None
        source_file_id = str(sf["id"])
        chunk_id = str(sf["knowledge_chunk_id"])
        assert chunk_id
        assert str(sf["doctype_token"]) == "invoice"
        assert str(sf["correspondent_token"]) == "supplier-42"
        assert sf["autotag_applied_at"] is not None
    finally:
        con.close()

    # Second apply must not duplicate assignments.
    second = autotag_apply_for_source_file(
        "TENANT_A",
        source_file_id=source_file_id,
        actor_user_id="dev",
        route_key="source_scan",
    )
    assert second["ok"] is True

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        assignments = con.execute(
            """
            SELECT COUNT(*) AS c
            FROM tag_assignments
            WHERE tenant_id='TENANT_A' AND entity_type='knowledge_chunk' AND entity_id=?
            """,
            (chunk_id,),
        ).fetchone()
        assert assignments is not None
        assert int(assignments["c"]) == 1
    finally:
        con.close()
