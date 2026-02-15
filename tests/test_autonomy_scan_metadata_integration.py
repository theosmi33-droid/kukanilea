from __future__ import annotations

import json
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


def test_scan_writes_filename_metadata_json(tmp_path: Path, monkeypatch) -> None:
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
    file_name = "Rechnung_2026-02-15_KD-1234.pdf"
    (docs / file_name).write_bytes(b"%PDF-1.4\nFake")

    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT metadata_json
            FROM source_files
            WHERE tenant_id='TENANT_A' AND source_kind='document'
            ORDER BY first_seen_at DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    metadata_raw = str(row["metadata_json"] or "")
    assert len(metadata_raw.encode("utf-8")) <= 1024
    metadata = json.loads(metadata_raw)
    assert metadata.get("doctype") == "invoice"
    assert metadata.get("date_iso") == "2026-02-15"
    assert metadata.get("customer_token") == "KD-1234"
