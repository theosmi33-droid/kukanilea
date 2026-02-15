from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

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
                "readonly.png",
                "hash-7",
                "fp-7",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_blocks_when_read_only(tmp_path: Path) -> None:
    _init_core(tmp_path)
    source_file_id = "sf7"
    _insert_source_file("TENANT_A", source_file_id)
    image_path = tmp_path / "readonly.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", READ_ONLY=True)
    with app.app_context():
        raised = False
        try:
            submit_ocr_for_source_file(
                tenant_id="TENANT_A",
                actor_user_id="dev",
                source_file_id=source_file_id,
                abs_path=image_path,
            )
        except PermissionError as exc:
            raised = True
            assert str(exc) == "read_only"
    assert raised is True
