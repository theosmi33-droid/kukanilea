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


def _auth(client, tenant: str) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = tenant


def test_oversize_eml_returns_413(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", MAX_EML_BYTES=1024)
    client = app.test_client()
    _auth(client, "TENANT_A")

    payload = b"From: a@a\nTo: b@b\nSubject: S\n\n" + (b"x" * 2000)
    data = {"file": (io.BytesIO(payload), "mail.eml")}
    resp = client.post(
        "/api/emails/import", data=data, content_type="multipart/form-data"
    )
    assert resp.status_code == 413
    body = resp.get_json() or {}
    assert body.get("error", {}).get("code") == "payload_too_large"


def test_malformed_email_does_not_crash_and_truncates(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", MAX_EML_BYTES=1024 * 1024)
    client = app.test_client()
    _auth(client, "TENANT_A")

    huge = (
        b"From: a@a\nTo: b@b\nSubject: S\nContent-Type: text/plain\n\n" + b"A" * 25000
    )
    data = {"file": (io.BytesIO(huge), "mail.eml")}
    resp = client.post(
        "/api/emails/import", data=data, content_type="multipart/form-data"
    )
    assert resp.status_code == 200

    email_id = (resp.get_json() or {}).get("email_id")
    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT body_text, raw_eml, attachments_json FROM emails_cache WHERE id=?",
            (email_id,),
        ).fetchone()
        assert row is not None
        body = row["body_text"] or ""
        assert "[truncated]" in body
        assert len(body) <= 20020
        assert row["attachments_json"] is not None
        # raw storage is bounded and does not persist full oversized payload
        assert len(row["raw_eml"] or b"") <= 65536
    finally:
        con.close()
