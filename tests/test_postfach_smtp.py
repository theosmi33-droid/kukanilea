from __future__ import annotations

from pathlib import Path

from app.mail.postfach_smtp import send_draft
from app.mail.postfach_store import (
    create_account,
    create_draft,
    get_thread,
    list_threads,
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
