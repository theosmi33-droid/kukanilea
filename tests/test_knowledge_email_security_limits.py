from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.knowledge.core import knowledge_policy_update


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
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        READ_ONLY=False,
        KNOWLEDGE_EMAIL_MAX_BYTES=512,
    )
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    with app.app_context():
        knowledge_policy_update(
            "TENANT_A",
            actor_user_id="dev",
            allow_customer_pii=True,
            allow_email=True,
        )
    return client


def test_oversize_upload_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    eml = b"From:a@x.tld\nTo:b@y.tld\nSubject:x\n\n" + (b"x" * 4096)
    resp = client.post(
        "/knowledge/email/upload",
        data={"file": (io.BytesIO(eml), "big.eml")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413


def test_subject_newline_sanitized(tmp_path: Path) -> None:
    client = _client(tmp_path)
    eml = (
        b"From:a@x.tld\nTo:b@y.tld\n"
        b"Subject: Hello\r\nBcc: injected@evil.tld\n\n"
        b"Body with enough text to pass minimal threshold Body with enough text to pass."
    )
    resp = client.post(
        "/knowledge/email/upload",
        data={"file": (io.BytesIO(eml), "ok.eml")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT subject_redacted FROM knowledge_email_sources WHERE tenant_id='TENANT_A' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        subject = str(row["subject_redacted"] or "")
        assert "\r" not in subject
        assert "\n" not in subject
    finally:
        con.close()
