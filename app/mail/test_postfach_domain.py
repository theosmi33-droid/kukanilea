from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from app.mail import postfach_imap, sync_engine


def test_extract_body_and_attachments_detects_attachment():
    msg = EmailMessage()
    msg["From"] = "a@example.com"
    msg["To"] = "b@example.com"
    msg["Subject"] = "s"
    msg.set_content("Plain body")
    msg.add_attachment(
        b"binary-data",
        maintype="application",
        subtype="pdf",
        filename="angebot.pdf",
    )

    body, attachments = postfach_imap._extract_body_and_attachments(msg)  # noqa: SLF001
    assert "Plain body" in body
    assert len(attachments) == 1
    assert attachments[0]["filename"] == "angebot.pdf"
    assert attachments[0]["size_bytes"] > 0


def test_sync_account_offline_safe_on_connect_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "test-key")
    db_path = tmp_path / "core.sqlite3"
    with patch("app.mail.postfach_store.ensure_postfach_schema"), patch(
        "app.mail.postfach_store.email_encryption_ready", return_value=True
    ), patch(
        "app.mail.postfach_store.get_account",
        return_value={"id": "acc1", "imap_username": "u@example.com"},
    ), patch(
        "app.mail.postfach_imap._resolve_auth",
        return_value={"ok": True, "kind": "password", "username": "u@example.com", "password": "x"},
    ), patch(
        "app.mail.postfach_imap.connect", side_effect=OSError("offline")
    ), patch("app.mail.postfach_store.update_account_sync_report"):
        result = postfach_imap.sync_account(
            db_path,
            tenant_id="tenant_a",
            account_id="acc1",
            limit=10,
        )
    assert result["ok"] is False
    assert result["reason"] == "imap_sync_failed"


def test_sync_all_accounts_aggregates_results():
    with patch(
        "app.mail.postfach_store.ensure_postfach_schema"
    ), patch(
        "app.mail.postfach_store.list_accounts",
        return_value=[{"id": "a1"}, {"id": "a2"}],
    ), patch(
        "app.mail.postfach_imap.sync_account",
        side_effect=[
            {"ok": True, "imported": 3, "duplicates": 1},
            {"ok": False, "imported": 0, "duplicates": 0},
        ],
    ):
        out = sync_engine.sync_all_accounts(
            Path("/tmp/core.sqlite3"),
            tenant_id="tenant_a",
            limit_per_account=20,
            auto_download_attachments=False,
        )
    assert out["accounts_total"] == 2
    assert out["accounts_failed"] == 1
    assert out["imported"] == 3
    assert out["duplicates"] == 1
