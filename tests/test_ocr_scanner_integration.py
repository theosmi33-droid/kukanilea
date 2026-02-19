from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy import ocr as ocr_mod
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _mock_tesseract_binary(monkeypatch) -> None:
    def _resolve(requested_bin=None, env=None, *, platform_name=None):
        selected = str(requested_bin or "/usr/bin/tesseract")
        source = "explicit" if requested_bin else "path"
        return ocr_mod.ResolvedTesseractBin(
            requested=requested_bin,
            resolved_path=selected,
            exists=True,
            executable=True,
            allowlisted=True,
            allowlist_reason="matched_prefix",
            allowed_prefixes=("/usr/bin",),
            resolution_source=source,
        )

    monkeypatch.setattr(ocr_mod, "resolve_tesseract_binary", _resolve)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_source_scan_runs_ocr_for_supported_images(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-key")
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_documents=True,
        allow_customer_pii=True,
        allow_ocr=True,
    )

    class _Proc:
        returncode = 0
        stdout = "OCR text"
        stderr = ""

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.subprocess, "run", lambda *_a, **_k: _Proc())

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\npayload")
    source_watch_config_update(
        "TENANT_A", documents_inbox_dir=str(docs_dir), enabled=True
    )

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) >= 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        ocr_jobs = con.execute(
            "SELECT COUNT(*) AS c FROM autonomy_ocr_jobs WHERE tenant_id='TENANT_A' AND status='done'"
        ).fetchone()
        assert int(ocr_jobs["c"]) >= 1
        row = con.execute(
            """
            SELECT ocr_knowledge_chunk_id
            FROM source_files
            WHERE tenant_id='TENANT_A' AND source_kind='document'
            ORDER BY last_seen_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert str(row["ocr_knowledge_chunk_id"] or "")
    finally:
        con.close()
