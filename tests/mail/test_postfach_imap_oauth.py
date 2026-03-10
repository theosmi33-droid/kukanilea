from __future__ import annotations

from unittest.mock import patch

from app.mail import postfach_imap


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
