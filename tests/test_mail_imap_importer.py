from __future__ import annotations

from pathlib import Path

from app.mail import (
    ensure_mail_schema,
    list_messages,
    save_account,
    sync_account,
)


class _FakeIMAP:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def login(self, username: str, password: str):
        return ("OK", [b"logged"])

    def select(self, mailbox: str):
        return ("OK", [b"1"])

    def uid(self, command: str, *args):
        cmd = command.lower()
        if cmd == "search":
            return ("OK", [b"1001"])
        if cmd == "fetch":
            raw = (
                b"From: Alice <alice@example.com>\r\n"
                b"To: Bob <bob@example.com>\r\n"
                b"Subject: Hello World\r\n"
                b"Message-ID: <x1@example.com>\r\n"
                b"\r\n"
                b"My phone is +49 151 12345678\r\n"
            )
            return ("OK", [(b"1001 (RFC822 {120}", raw), b")"])
        return ("NO", [])


def test_sync_account_imports_redacted_messages(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    ensure_mail_schema(db_path)
    account_id = save_account(
        db_path,
        tenant_id="TENANT_A",
        label="Demo",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        auth_mode="password",
        imap_password_ref=None,
    )

    monkeypatch.setattr("app.mail.imap_importer.imaplib.IMAP4_SSL", _FakeIMAP)
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        password="secret",
        limit=10,
    )
    assert result["ok"] is True
    assert int(result["imported"]) >= 1

    rows = list_messages(db_path, "TENANT_A", account_id=account_id, limit=10)
    assert rows
    row = rows[0]
    assert "alice@example.com" not in row["from_redacted"].lower()
    assert "hello world" in row["subject_redacted"].lower()
