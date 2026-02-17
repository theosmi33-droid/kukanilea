from __future__ import annotations

from pathlib import Path

import app.web as webmod
from app import create_app
from app.mail.postfach_store import (
    create_account,
    create_draft,
    get_draft,
    get_oauth_token,
)


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


def _set_core_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    webmod.core.DB_PATH = db_path
    return db_path


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


def test_postfach_page_renders() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    res = client.get("/postfach")
    assert res.status_code == 200
    assert b"Postfach Hub" in res.data


def test_mail_route_redirects_to_postfach() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    res = client.get("/mail", follow_redirects=False)
    assert res.status_code in {301, 302}
    assert "/postfach" in str(res.headers.get("Location") or "")


def test_postfach_account_add_fails_closed_without_key(monkeypatch) -> None:
    monkeypatch.delenv("EMAIL_ENCRYPTION_KEY", raising=False)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    res = client.post(
        "/postfach/accounts/add",
        data={
            "label": "Demo",
            "imap_host": "imap.example.com",
            "imap_port": "993",
            "imap_username": "user@example.com",
            "secret": "pass",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"EMAIL_ENCRYPTION_KEY" in res.data


def test_postfach_oauth_start_sets_session_and_redirects(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        GOOGLE_CLIENT_ID="google-client-id",
        GOOGLE_CLIENT_SECRET="google-client-secret",
        OAUTH_REDIRECT_BASE="http://127.0.0.1:5051",
    )
    db_path = _set_core_db(tmp_path)
    account_id = create_account(
        db_path,
        tenant_id="KUKANILEA",
        label="OAuth Google",
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
    monkeypatch.setattr(
        "app.web.postfach_build_authorization_url",
        lambda **kwargs: "https://accounts.google.com/o/oauth2/v2/auth?state=test",
    )
    client = app.test_client()
    _login(client)
    res = client.post(
        "/postfach/accounts/oauth/start",
        data={"account_id": account_id},
        follow_redirects=False,
    )
    assert res.status_code in {301, 302}
    assert "accounts.google.com" in str(res.headers.get("Location") or "")
    with client.session_transaction() as sess:
        assert str(sess.get("postfach_oauth_account_id") or "") == account_id
        assert str(sess.get("postfach_oauth_provider") or "") == "google"
        assert str(sess.get("postfach_oauth_state") or "").strip()
        assert str(sess.get("postfach_oauth_verifier") or "").strip()


def test_postfach_oauth_callback_saves_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        GOOGLE_CLIENT_ID="google-client-id",
        GOOGLE_CLIENT_SECRET="google-client-secret",
        OAUTH_REDIRECT_BASE="http://127.0.0.1:5051",
    )
    db_path = _set_core_db(tmp_path)
    account_id = create_account(
        db_path,
        tenant_id="KUKANILEA",
        label="OAuth Google",
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
    monkeypatch.setattr(
        "app.web.postfach_exchange_code_for_tokens",
        lambda **kwargs: {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "scopes": ["https://mail.google.com/"],
            "token_type": "Bearer",
        },
    )
    client = app.test_client()
    _login(client)
    with client.session_transaction() as sess:
        sess["postfach_oauth_state"] = "state-123"
        sess["postfach_oauth_verifier"] = "verifier-123"
        sess["postfach_oauth_account_id"] = account_id
        sess["postfach_oauth_provider"] = "google"

    res = client.get(
        "/postfach/accounts/oauth/callback?state=state-123&code=auth-code-123",
        follow_redirects=False,
    )
    assert res.status_code in {301, 302}
    token = get_oauth_token(
        db_path,
        tenant_id="KUKANILEA",
        account_id=account_id,
        provider="google",
    )
    assert token is not None
    assert token["access_token"] == "access-token"


def test_postfach_send_requires_safety_ack_when_warnings_exist(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("EMAIL_ENCRYPTION_KEY", "dev-secret-key")
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    db_path = _set_core_db(tmp_path)
    account_id = create_account(
        db_path,
        tenant_id="KUKANILEA",
        label="SMTP",
        imap_host="imap.example.com",
        imap_port=993,
        imap_username="sender@example.com",
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_username="sender@example.com",
        smtp_use_ssl=True,
        secret_plain="secret",
    )
    draft_id = create_draft(
        db_path,
        tenant_id="KUKANILEA",
        account_id=account_id,
        thread_id=None,
        to_value="recipient@other-domain.com",
        subject_value="Angebot",
        body_value="Link: https://bit.ly/test und IBAN DE89370400440532013000",
    )
    client = app.test_client()
    _login(client)
    blocked = client.post(
        "/postfach/drafts/send",
        data={
            "draft_id": draft_id,
            "account_id": account_id,
            "thread_id": "",
            "user_confirmed": "1",
        },
        follow_redirects=True,
    )
    assert blocked.status_code == 200
    assert b"Sicherheitscheck" in blocked.data
    draft = get_draft(
        db_path,
        tenant_id="KUKANILEA",
        draft_id=draft_id,
        include_plain=False,
    )
    assert draft is not None
    assert str(draft.get("status") or "") == "draft"

    _FakeSMTPSSL.sent_count = 0
    monkeypatch.setattr("app.mail.postfach_smtp.smtplib.SMTP_SSL", _FakeSMTPSSL)
    sent = client.post(
        "/postfach/drafts/send",
        data={
            "draft_id": draft_id,
            "account_id": account_id,
            "thread_id": "",
            "user_confirmed": "1",
            "safety_ack": "1",
        },
        follow_redirects=True,
    )
    assert sent.status_code == 200
    assert b"Entwurf versendet" in sent.data
    assert _FakeSMTPSSL.sent_count == 1
