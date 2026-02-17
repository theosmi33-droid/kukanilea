from __future__ import annotations

import base64
import ssl
from pathlib import Path

from app.mail.postfach_imap import sync_account
from app.mail.postfach_store import (
    create_account,
    get_account,
    get_thread,
    list_threads,
    save_oauth_token,
)


class _FakeIMAP:
    def __init__(self, host: str, port: int, **kwargs):
        self.host = host
        self.port = port
        self.kwargs = kwargs

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
            raw = Path("tests/fixtures/postfach_sample.eml").read_bytes()
            return ("OK", [(b"1001 (RFC822 {120}", raw), b")"])
        return ("NO", [])


class _RecordingIMAP(_FakeIMAP):
    saw_ssl_context = False

    def __init__(self, host: str, port: int, **kwargs):
        super().__init__(host, port, **kwargs)
        _RecordingIMAP.saw_ssl_context = isinstance(
            kwargs.get("ssl_context"), ssl.SSLContext
        )


class _OAuthIMAP(_FakeIMAP):
    saw_mechanism = ""
    saw_payload = ""

    def authenticate(self, mechanism: str, auth_cb):
        _OAuthIMAP.saw_mechanism = mechanism
        encoded = auth_cb(None).decode("utf-8", errors="ignore")
        _OAuthIMAP.saw_payload = base64.b64decode(encoded).decode(
            "utf-8", errors="ignore"
        )
        return ("OK", [b"authenticated"])


def test_postfach_sync_imports_thread_and_redacts(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="Demo",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="user@example.com",
        smtp_use_ssl=True,
        secret_plain="secret",
    )

    monkeypatch.setattr("app.mail.postfach_imap.imaplib.IMAP4_SSL", _FakeIMAP)
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        limit=10,
    )
    assert result["ok"] is True
    assert int(result["imported"]) >= 1

    threads = list_threads(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        limit=10,
    )
    assert threads
    thread_data = get_thread(db_path, tenant_id="TENANT_A", thread_id=threads[0]["id"])
    assert thread_data is not None
    msg = thread_data["messages"][0]
    assert "alice@example.com" not in str(msg["from_redacted"]).lower()
    assert "[redacted-email]" in str(msg["redacted_text"]).lower()


def test_postfach_sync_fail_closed_without_key(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="Demo",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="user@example.com",
        smtp_use_ssl=True,
        secret_plain="secret",
    )
    monkeypatch.delenv("EMAIL_ENCRYPTION_KEY", raising=False)
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        limit=1,
    )
    assert result["ok"] is False
    assert result["reason"] == "email_encryption_key_missing"


def test_postfach_sync_uses_ssl_context(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="SSL",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="user@example.com",
        smtp_use_ssl=True,
        secret_plain="secret",
    )
    _RecordingIMAP.saw_ssl_context = False
    monkeypatch.setattr("app.mail.postfach_imap.imaplib.IMAP4_SSL", _RecordingIMAP)
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        limit=1,
    )
    assert result["ok"] is True
    assert _RecordingIMAP.saw_ssl_context is True


def test_postfach_sync_oauth_requires_token(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="OAuth",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_username="user@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        smtp_username="user@example.com",
        smtp_use_ssl=True,
        secret_plain="",
        auth_mode="oauth_google",
        oauth_provider="google",
    )
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        limit=1,
    )
    assert result["ok"] is False
    assert result["reason"] == "oauth_token_missing"
    account = get_account(db_path, "TENANT_A", account_id)
    assert account is not None
    assert str(account.get("oauth_status")) in {"error", "not_connected"}


def test_postfach_sync_oauth_uses_xoauth2(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="OAuth",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_username="user@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        smtp_username="user@example.com",
        smtp_use_ssl=True,
        secret_plain="",
        auth_mode="oauth_google",
        oauth_provider="google",
    )
    save_oauth_token(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        provider="google",
        access_token="access-token-123",
        refresh_token="refresh-token-123",
        expires_at="2099-01-01T00:00:00+00:00",
        scopes=["https://mail.google.com/"],
        token_type="Bearer",
    )
    _OAuthIMAP.saw_mechanism = ""
    _OAuthIMAP.saw_payload = ""
    monkeypatch.setattr("app.mail.postfach_imap.imaplib.IMAP4_SSL", _OAuthIMAP)
    result = sync_account(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        limit=1,
    )
    assert result["ok"] is True
    assert _OAuthIMAP.saw_mechanism == "XOAUTH2"
    assert "auth=Bearer access-token-123" in _OAuthIMAP.saw_payload
