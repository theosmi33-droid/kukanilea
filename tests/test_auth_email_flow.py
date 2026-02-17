from __future__ import annotations

from app import create_app
from app.config import Config


def _extract_code(text: str) -> str:
    marker = "Code:"
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].strip().split()[0]


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    return app


def test_register_verify_and_login_via_email(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()

    resp = client.post(
        "/register",
        data={
            "email": "newuser@example.com",
            "password": "secret1234",
            "password_confirm": "secret1234",
        },
    )
    assert resp.status_code == 200
    assert b"Registrierung gespeichert" in resp.data

    auth_db = app.extensions["auth_db"]
    outbox = auth_db.list_outbox(limit=5)
    assert outbox
    verify = outbox[0]
    assert verify["kind"] == "verify_email"
    code = _extract_code(verify["body"])
    assert code

    resp_verify = client.post(
        "/verify-email", data={"email": "newuser@example.com", "code": code}
    )
    assert resp_verify.status_code == 200
    assert b"E-Mail best\xc3\xa4tigt" in resp_verify.data

    login = client.post(
        "/login",
        data={"username": "newuser@example.com", "password": "secret1234"},
    )
    assert login.status_code == 302
    assert login.headers["Location"].endswith("/")


def test_forgot_and_reset_password_flow(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()

    client.post(
        "/register",
        data={
            "email": "resetme@example.com",
            "password": "secret1234",
            "password_confirm": "secret1234",
        },
    )
    auth_db = app.extensions["auth_db"]
    verify_code = _extract_code(auth_db.list_outbox(limit=1)[0]["body"])
    client.post(
        "/verify-email", data={"email": "resetme@example.com", "code": verify_code}
    )

    forgot = client.post("/forgot-password", data={"email": "resetme@example.com"})
    assert forgot.status_code == 200
    assert b"Wenn der Account existiert" in forgot.data

    outbox = auth_db.list_outbox(limit=5)
    reset_rows = [row for row in outbox if row["kind"] == "reset_password"]
    assert reset_rows
    reset_code = _extract_code(reset_rows[0]["body"])
    assert reset_code

    reset = client.post(
        "/reset-password",
        data={
            "email": "resetme@example.com",
            "code": reset_code,
            "password": "newpass1234",
            "password_confirm": "newpass1234",
        },
    )
    assert reset.status_code == 200
    assert b"Passwort aktualisiert" in reset.data

    login = client.post(
        "/login", data={"username": "resetme@example.com", "password": "newpass1234"}
    )
    assert login.status_code == 302
