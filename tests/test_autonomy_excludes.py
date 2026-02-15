from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _enable_docs_policy() -> None:
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_documents=True,
    )


def test_scan_respects_default_exclude_globs(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    _enable_docs_policy()
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")

    docs = tmp_path / "docs"
    (docs / ".git").mkdir(parents=True, exist_ok=True)
    (docs / "__pycache__").mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)

    (docs / ".git" / "config.txt").write_text("hidden", encoding="utf-8")
    (docs / "__pycache__" / "x.txt").write_text("cache", encoding="utf-8")
    (docs / "ok.txt").write_text("normal content", encoding="utf-8")

    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1
    assert int(result["skipped_exclude"]) == 2

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        excluded = con.execute(
            """
            SELECT COUNT(*) AS n FROM source_ingest_log
            WHERE tenant_id='TENANT_A' AND action='skipped_exclude' AND detail_code='exclude'
            """
        ).fetchone()["n"]
        chunks = con.execute(
            """
            SELECT COUNT(*) AS n FROM knowledge_chunks
            WHERE tenant_id='TENANT_A' AND source_type='document'
            """
        ).fetchone()["n"]
        assert int(excluded) == 2
        assert int(chunks) == 1
    finally:
        con.close()
