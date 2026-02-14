from __future__ import annotations

import io
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


def _client(tmp_path: Path):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_ics_upload_denied_when_policy_off_and_no_rows_written(tmp_path: Path) -> None:
    client = _client(tmp_path)
    data = b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:X\nEND:VEVENT\nEND:VCALENDAR\n"
    resp = client.post(
        "/knowledge/ics/upload",
        data={"file": (io.BytesIO(data), "sample.ics")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 403

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        n = con.execute("SELECT COUNT(*) FROM knowledge_ics_sources").fetchone()[0]
        assert int(n) == 0
    finally:
        con.close()
