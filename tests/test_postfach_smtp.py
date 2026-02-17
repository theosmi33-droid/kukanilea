from __future__ import annotations

from pathlib import Path

from app.mail.postfach_smtp import send_draft
from app.mail.postfach_store import (
    create_account,
    create_draft,
    get_thread,
    list_threads,
    save_oauth_token,
)


class _FakeSMTPSSL:
    sent_count = 0

    def __init__(self, host: str, port: int, **kwargs):
        self.host = host
        self.port = port
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def login(self, username: str, password: str):
        return (235, b"ok")

    def send_message(self, message):
        _FakeSMTPSSL.sent_count += 1
        return {}


class _FakeSMTPOAuth(_FakeSMTPSSL):
    auth_calls = 0
    auth_payload = ""

    def docmd(self, command: str, arg: str | None = None):
        if command == "AUTH" and arg and arg.startswith("XOAUTH2 "):
            _FakeSMTPOAuth.auth_calls += 1
            _FakeSMTPOAuth.auth_payload = arg
            return (235, b"ok")
        return (500, b"unsupported")

    def send_message(self, message):
        _FakeSMTPOAuth.sent_count += 1
        return {}


def _setup_account_and_draft(tmp_path: Path) -> tuple[Path, str, str, str]:
    db_path = tmp_path / "core.sqlite3"
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="SMTP",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="user@example.com",
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="sender@example.com",
        smtp_use_ssl=True,
        secret_plain="secret",
    )
    draft_id = create_draft(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        thread_id=None,
        to_value="recipient@example.com",
        subject_value="Angebot",
        body_value="Hier ist der Entwurf.",
    )
    return db_path, "TENANT_A", account_id, draft_id


def test_send_draft_requires_user_confirmation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path, tenant_id, _account_id, draft_id = _setup_account_and_draft(tmp_path)
    result = send_draft(
        db_path,
        tenant_id=tenant_id,
        draft_id=draft_id,
        user_confirmed=False,
    )
    assert result["ok"] is False
    assert result["reason"] == "user_confirmation_required"


def test_send_draft_uses_smtp_ssl_and_stores_message(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path, tenant_id, account_id, draft_id = _setup_account_and_draft(tmp_path)
    _FakeSMTPSSL.sent_count = 0
    monkeypatch.setattr("app.mail.postfach_smtp.smtplib.SMTP_SSL", _FakeSMTPSSL)
    result = send_draft(
        db_path,
        tenant_id=tenant_id,
        draft_id=draft_id,
        user_confirmed=True,
    )
    assert result["ok"] is True
    assert _FakeSMTPSSL.sent_count == 1

    threads = list_threads(
        db_path,
        tenant_id=tenant_id,
        account_id=account_id,
        limit=10,
    )
    assert threads
    data = get_thread(db_path, tenant_id=tenant_id, thread_id=threads[0]["id"])
    assert data is not None
    assert data["messages"]
    assert data["messages"][0]["direction"] == "outbound"


def test_send_draft_fail_closed_without_encryption_key(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path, tenant_id, _account_id, draft_id = _setup_account_and_draft(tmp_path)
    monkeypatch.delenv("EMAIL_ENCRYPTION_KEY", raising=False)
    result = send_draft(
        db_path,
        tenant_id=tenant_id,
        draft_id=draft_id,
        user_confirmed=True,
    )
    assert result["ok"] is False
    assert result["reason"] == "email_encryption_key_missing"


def test_send_draft_oauth_requires_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path = tmp_path / "core.sqlite3"
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="SMTP OAuth",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_username="sender@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        smtp_username="sender@example.com",
        smtp_use_ssl=True,
        secret_plain="",
        auth_mode="oauth_google",
        oauth_provider="google",
    )
    draft_id = create_draft(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        thread_id=None,
        to_value="recipient@example.com",
        subject_value="OAuth Draft",
        body_value="Bitte pruefen.",
    )
    result = send_draft(
        db_path,
        tenant_id="TENANT_A",
        draft_id=draft_id,
        user_confirmed=True,
    )
    assert result["ok"] is False
    assert result["reason"] == "oauth_token_missing"


def test_send_draft_oauth_uses_xoauth2_auth(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path = tmp_path / "core.sqlite3"
    account_id = create_account(
        db_path,
        tenant_id="TENANT_A",
        label="SMTP OAuth",
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_username="sender@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        smtp_username="sender@example.com",
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
        access_token="oauth-access-token",
        refresh_token="oauth-refresh-token",
        expires_at="2099-01-01T00:00:00+00:00",
        scopes=["https://mail.google.com/"],
        token_type="Bearer",
    )
    draft_id = create_draft(
        db_path,
        tenant_id="TENANT_A",
        account_id=account_id,
        thread_id=None,
        to_value="recipient@example.com",
        subject_value="OAuth Draft",
        body_value="Bitte pruefen.",
    )
    _FakeSMTPOAuth.sent_count = 0
    _FakeSMTPOAuth.auth_calls = 0
    _FakeSMTPOAuth.auth_payload = ""
    monkeypatch.setattr("app.mail.postfach_smtp.smtplib.SMTP_SSL", _FakeSMTPOAuth)
    result = send_draft(
        db_path,
        tenant_id="TENANT_A",
        draft_id=draft_id,
        user_confirmed=True,
    )
    assert result["ok"] is True
    assert _FakeSMTPOAuth.auth_calls == 1
    assert "XOAUTH2 " in _FakeSMTPOAuth.auth_payload
    assert _FakeSMTPOAuth.sent_count == 1
