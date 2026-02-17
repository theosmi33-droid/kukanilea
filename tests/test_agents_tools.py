from __future__ import annotations

from pathlib import Path

from app.agents import tools
from app.config import Config
from app.mail.postfach_store import create_account, create_draft


def test_tools_validation_error():
    out = tools.dispatch(
        "create_task",
        {},
        read_only_flag=False,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "validation_error"


def test_tools_read_only_blocks_mutating():
    out = tools.dispatch(
        "create_task",
        {"title": "A"},
        read_only_flag=True,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "read_only"


def test_export_akte_is_mutating_and_blocked():
    out = tools.dispatch(
        "export_akte",
        {"task_id": 1},
        read_only_flag=True,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "read_only"


class _FakeSMTPSSL:
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
        return {}


def test_postfach_send_draft_requires_confirmation(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(Config, "CORE_DB", db_path)
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    account_id = create_account(
        db_path,
        tenant_id="kukanilea",
        label="Demo",
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
        tenant_id="kukanilea",
        account_id=account_id,
        thread_id=None,
        to_value="recipient@example.com",
        subject_value="Angebot",
        body_value="Entwurf",
    )
    out = tools.dispatch(
        "postfach_send_draft",
        {"draft_id": draft_id, "user_confirmed": False},
        read_only_flag=False,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "tool_failed"
    assert "user_confirmation_required" in out["error"]["msg"]


def test_postfach_send_draft_success_with_confirmation(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(Config, "CORE_DB", db_path)
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    monkeypatch.setattr("app.mail.postfach_smtp.smtplib.SMTP_SSL", _FakeSMTPSSL)
    account_id = create_account(
        db_path,
        tenant_id="kukanilea",
        label="Demo",
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
        tenant_id="kukanilea",
        account_id=account_id,
        thread_id=None,
        to_value="recipient@example.com",
        subject_value="Angebot",
        body_value="Entwurf",
    )
    out = tools.dispatch(
        "postfach_send_draft",
        {"draft_id": draft_id, "user_confirmed": True},
        read_only_flag=False,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"] is None
    assert out["result"]["ok"] is True
