from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path, read_only: bool = False):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_email_upload_denied_when_policy_off_and_no_rows_written(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    eml = b"From: a@example.com\nTo: b@example.com\nSubject: Test\n\nHallo"
    resp = client.post(
        "/knowledge/email/upload",
        data={"file": (eml, "sample.eml")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 403

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        n = con.execute("SELECT COUNT(*) FROM knowledge_email_sources").fetchone()[0]
        assert int(n) == 0
    finally:
        con.close()
