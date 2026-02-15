from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.autonomy.ocr import submit_ocr_for_source_file
from app.knowledge.core import knowledge_policy_update


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
                "large.png",
                "hash-3",
                "fp-3",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_rejects_oversized_input(tmp_path: Path) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf3"
    _insert_source_file("TENANT_A", source_file_id)
    image_path = tmp_path / "large.png"
    image_path.write_bytes(b"\x89PNG" + (b"A" * 64))

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", AUTONOMY_OCR_MAX_BYTES=16)
    with app.app_context():
        result = submit_ocr_for_source_file(
            tenant_id="TENANT_A",
            actor_user_id="dev",
            source_file_id=source_file_id,
            abs_path=image_path,
        )
    assert result["ok"] is False
    assert result["error_code"] == "too_large"

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT status, error_code
            FROM autonomy_ocr_jobs
            WHERE tenant_id='TENANT_A' AND source_file_id=?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (source_file_id,),
        ).fetchone()
        assert row is not None
        assert str(row["status"]) == "failed"
        assert str(row["error_code"]) == "too_large"
    finally:
        con.close()
