from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.autotag import autotag_rule_create
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_autotag_engine_matches_expected_files(tmp_path: Path, monkeypatch) -> None:
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
        name="Invoice By Filename",
        priority=10,
        condition_obj={
            "all": [
                {"type": "filename_glob", "pattern": "*rechnung*"},
                {"type": "ext_in", "values": ["txt"]},
            ]
        },
        action_list=[{"type": "add_tag", "tag_name": "invoice"}],
        actor_user_id="dev",
    )

    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "rechnung_2026-02-15.txt").write_text("A", encoding="utf-8")
    (docs / "bericht_2026-02-15.txt").write_text("B", encoding="utf-8")
    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 2

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        tagged = con.execute(
            """
            SELECT sf.basename, ta.id AS assignment_id
            FROM source_files sf
            LEFT JOIN tag_assignments ta
              ON ta.tenant_id=sf.tenant_id
             AND ta.entity_type='knowledge_chunk'
             AND ta.entity_id=sf.knowledge_chunk_id
            WHERE sf.tenant_id='TENANT_A'
            ORDER BY sf.basename ASC
            """
        ).fetchall()
    finally:
        con.close()

    assert len(tagged) == 2
    by_name = {str(r["basename"]): bool(r["assignment_id"]) for r in tagged}
    assert by_name["rechnung_2026-02-15.txt"] is True
    assert by_name["bericht_2026-02-15.txt"] is False


def test_autotag_rule_validation_rejects_unknown_condition(tmp_path: Path) -> None:
    _init_core(tmp_path)
    try:
        autotag_rule_create(
            "TENANT_A",
            name="Bad Rule",
            priority=0,
            condition_obj={"type": "unknown_kind", "x": 1},
            action_list=[{"type": "set_doctype", "token": "invoice"}],
            actor_user_id="dev",
        )
    except ValueError as exc:
        assert str(exc) == "validation_error"
    else:
        raise AssertionError("expected validation_error")
