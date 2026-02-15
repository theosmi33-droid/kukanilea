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


def test_source_scan_dedupe_hash_and_size(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_documents=True,
    )

    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    content = "identical-body"
    (docs / "a.txt").write_text(content, encoding="utf-8")
    (docs / "b.txt").write_text(content, encoding="utf-8")
    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1
    assert int(result["skipped_dedupe"]) == 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        files = con.execute(
            """
            SELECT id, duplicate_of_file_id, knowledge_chunk_id, basename
            FROM source_files
            WHERE tenant_id='TENANT_A'
            ORDER BY basename ASC
            """
        ).fetchall()
        assert len(files) == 2
        chunk_count = con.execute(
            """
            SELECT COUNT(*) AS c
            FROM knowledge_chunks
            WHERE tenant_id='TENANT_A' AND source_type='document'
            """
        ).fetchone()
        assert chunk_count is not None
        assert int(chunk_count["c"]) == 1

        dedup_rows = [r for r in files if r["duplicate_of_file_id"]]
        assert len(dedup_rows) == 1

        event = con.execute(
            """
            SELECT payload_json
            FROM events
            WHERE event_type='source_file_deduped'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        assert event is not None
        payload = str(event["payload_json"] or "")
        assert str(docs) not in payload
        assert "a.txt" not in payload
        assert "b.txt" not in payload
    finally:
        con.close()
