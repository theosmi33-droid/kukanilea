from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.ocr import submit_ocr_for_source_file


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _insert_source_file(tenant_id: str, source_file_id: str) -> None:
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            """
            INSERT INTO source_files(
              id, tenant_id, source_kind, basename, path_hash, fingerprint, status,
              last_seen_at, first_seen_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                source_file_id,
                tenant_id,
                "document",
                "sample.png",
                "hash-1",
                "fp-1",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_default_policy_is_deny(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    source_file_id = "sf1"
    _insert_source_file("TENANT_A", source_file_id)
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setenv("AUTONOMY_OCR_LANG", "eng")

    result = submit_ocr_for_source_file(
        tenant_id="TENANT_A",
        actor_user_id="dev",
        source_file_id=source_file_id,
        abs_path=image_path,
    )
    assert result["ok"] is False
    assert result["status"] == "skipped"
    assert result["error_code"] == "policy_denied"

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        job = con.execute(
            """
            SELECT status, error_code
            FROM autonomy_ocr_jobs
            WHERE tenant_id='TENANT_A' AND source_file_id=?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (source_file_id,),
        ).fetchone()
        assert job is not None
        assert str(job["status"]) == "skipped"
        assert str(job["error_code"]) == "policy_denied"
        cnt = con.execute(
            "SELECT COUNT(*) AS c FROM knowledge_chunks WHERE tenant_id='TENANT_A' AND source_type='ocr'"
        ).fetchone()
        assert int(cnt["c"]) == 0
    finally:
        con.close()
