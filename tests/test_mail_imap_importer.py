from __future__ import annotations

import base64
import json
import ssl
from pathlib import Path

from app.config import Config
from app.mail import (
    ensure_mail_schema,
    list_messages,
    load_secret,
    save_account,
    store_secret,
    sync_account,
)


class _FakeIMAP:
    def __init__(self, host: str, port: int, **_: object):
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


class _RecordingIMAP(_FakeIMAP):
    saw_ssl_context = False

    def __init__(self, host: str, port: int, **kwargs: object):
        super().__init__(host, port, **kwargs)
        ctx = kwargs.get("ssl_context")
        _RecordingIMAP.saw_ssl_context = isinstance(ctx, ssl.SSLContext)


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


def test_secret_storage_uses_encryption_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    ref = store_secret("super-secret")
    assert ref
    resolved = load_secret(ref)
    assert resolved == "super-secret"
    raw_file = (tmp_path / "secrets.json").read_text(encoding="utf-8")
    assert "super-secret" not in raw_file


def test_sync_uses_ssl_context(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    ensure_mail_schema(db_path)
    account_id = save_account(
        db_path,
        tenant_id="TENANT_A",
        label="SSL",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        auth_mode="password",
        imap_password_ref=None,
    )
    _RecordingIMAP.saw_ssl_context = False
    monkeypatch.setattr("app.mail.imap_importer.imaplib.IMAP4_SSL", _RecordingIMAP)
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        password="secret",
        limit=1,
    )
    assert result["ok"] is True
    assert _RecordingIMAP.saw_ssl_context is True


def test_load_secret_legacy_payload_requires_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    ref = "sec_legacy"
    legacy_payload = base64.b64encode(b"legacy-secret").decode("ascii")
    (tmp_path / "secrets.json").write_text(
        json.dumps({ref: legacy_payload}),
        encoding="utf-8",
    )
    monkeypatch.delenv("EMAIL_ENCRYPTION_KEY", raising=False)

    assert load_secret(ref) == ""
    saved = json.loads((tmp_path / "secrets.json").read_text(encoding="utf-8"))
    assert str(saved.get(ref) or "") == legacy_payload


def test_load_secret_legacy_payload_migrates_with_key(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    ref = "sec_legacy"
    legacy_payload = base64.b64encode(b"legacy-secret").decode("ascii")
    (tmp_path / "secrets.json").write_text(
        json.dumps({ref: legacy_payload}),
        encoding="utf-8",
    )

    assert load_secret(ref) == "legacy-secret"
    saved = json.loads((tmp_path / "secrets.json").read_text(encoding="utf-8"))
    migrated = str(saved.get(ref) or "")
    assert migrated.startswith("aesgcm:")
    assert "legacy-secret" not in migrated
