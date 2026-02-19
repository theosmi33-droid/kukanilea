from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.mail.postfach_store import (
    create_account,
    decrypt_account_secret,
    ensure_postfach_schema,
    get_account,
)


def _create_password_account(db_path: Path) -> str:
    return create_account(
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
        secret_plain="super-secret-value",
    )


def test_postfach_password_secret_is_encrypted_at_rest(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path = tmp_path / "core.sqlite3"
    account_id = _create_password_account(db_path)

    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT encrypted_secret FROM mailbox_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    encrypted_secret = str(row[0] or "")
    assert encrypted_secret.startswith("aesgcm:")
    assert "super-secret-value" not in encrypted_secret


def test_postfach_legacy_plaintext_secret_is_backfilled(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    db_path = tmp_path / "core.sqlite3"
    account_id = _create_password_account(db_path)

    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "UPDATE mailbox_accounts SET encrypted_secret=?, updated_at=? WHERE id=?",
            ("legacy-plaintext-secret", "2026-01-01T00:00:00+00:00", account_id),
        )
        con.commit()
    finally:
        con.close()

    ensure_postfach_schema(db_path)
    account = get_account(db_path, "TENANT_A", account_id)
    assert account is not None
    assert decrypt_account_secret(account) == "legacy-plaintext-secret"

    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT encrypted_secret FROM mailbox_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert str(row[0] or "").startswith("aesgcm:")


def test_postfach_create_account_fails_without_encryption_key(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("EMAIL_ENCRYPTION_KEY", raising=False)
    db_path = tmp_path / "core.sqlite3"
    with pytest.raises(ValueError, match="email_encryption_key_missing"):
        _create_password_account(db_path)
