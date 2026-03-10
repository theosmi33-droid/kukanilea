from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from app.mail import postfach_imap, postfach_store, sync_engine


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


def test_ingest_message_attachments_rejects_tenant_quota(tmp_path, monkeypatch):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(postfach_store.Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(postfach_store, "MAIL_ATTACHMENT_TENANT_QUOTA_BYTES", 10)

    refs: list[dict] = []

    def _capture_store(*args, **kwargs):
        refs.append(kwargs["content_ref"])
        return "att-1"

    with patch("app.mail.postfach_store.ensure_postfach_schema"), patch(
        "app.mail.postfach_store.store_message_attachment", side_effect=_capture_store
    ):
        out = postfach_store.ingest_message_attachments(
            db_path,
            tenant_id="tenant1",
            account_id="acc1",
            message_id="msg1",
            attachments=[
                {
                    "filename": "a.txt",
                    "mime_type": "text/plain",
                    "size_bytes": 11,
                    "content_bytes": b"hello world",
                }
            ],
        )

    assert out["processed"] == 1
    assert out["rejected"] == 1
    assert refs[0]["status"] == "rejected"
    assert refs[0]["reason"] == "tenant_quota_exceeded"


def test_ingest_message_attachments_rejects_oversized_payload(tmp_path, monkeypatch):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(postfach_store.Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(postfach_store, "MAIL_ATTACHMENT_TENANT_QUOTA_BYTES", 1024)
    monkeypatch.setattr(postfach_store, "MAX_FILE_SIZE", 5)

    refs: list[dict] = []

    def _capture_store(*args, **kwargs):
        refs.append(kwargs["content_ref"])
        return "att-2"

    with patch("app.mail.postfach_store.ensure_postfach_schema"), patch(
        "app.mail.postfach_store.store_message_attachment", side_effect=_capture_store
    ):
        out = postfach_store.ingest_message_attachments(
            db_path,
            tenant_id="tenant1",
            account_id="acc1",
            message_id="msg1",
            attachments=[
                {
                    "filename": "a.txt",
                    "mime_type": "text/plain",
                    "size_bytes": 6,
                    "content_bytes": b"123456",
                }
            ],
        )

    assert out["processed"] == 1
    assert out["rejected"] == 1
    assert refs[0]["status"] == "rejected"
    assert refs[0]["reason"] == "file_too_large"


def test_sync_account_oauth_authenticate_uses_raw_xoauth_payload(tmp_path, monkeypatch):
    class FakeImap:
        def __init__(self):
            self.decoded_payload = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def authenticate(self, mechanism, auth_cb):
            import base64

            assert mechanism == "XOAUTH2"
            callback_bytes = auth_cb(b"")
            wire_payload = base64.b64encode(callback_bytes)
            self.decoded_payload = base64.b64decode(wire_payload).decode("utf-8")
            return "OK", [b""]

        def select(self, *_args, **_kwargs):
            return "OK", [b""]

        def uid(self, command, *_args):
            if command == "search":
                return "OK", [b""]
            return "NO", []

    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "test-key")
    db_path = tmp_path / "core.sqlite3"
    fake = FakeImap()

    with patch("app.mail.postfach_store.ensure_postfach_schema"), patch(
        "app.mail.postfach_store.email_encryption_ready", return_value=True
    ), patch(
        "app.mail.postfach_store.get_account",
        return_value={"id": "acc1", "imap_username": "u@example.com"},
    ), patch(
        "app.mail.postfach_imap._resolve_auth",
        return_value={
            "ok": True,
            "kind": "xoauth2",
            "username": "u@example.com",
            "access_token": "token-123",
        },
    ), patch("app.mail.postfach_imap.connect", return_value=fake), patch(
        "app.mail.postfach_store.update_account_sync_cursor"
    ), patch("app.mail.postfach_store.update_account_sync_report"), patch(
        "app.mail.postfach_store.link_thread_customers_by_email", return_value={"linked": 0}
    ):
        result = postfach_imap.sync_account(
            db_path,
            tenant_id="tenant_a",
            account_id="acc1",
            limit=10,
        )

    assert result["ok"] is True
    assert fake.decoded_payload.startswith("user=u@example.com\x01auth=Bearer token-123")
