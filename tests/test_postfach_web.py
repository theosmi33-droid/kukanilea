from __future__ import annotations

from app import create_app


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


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
