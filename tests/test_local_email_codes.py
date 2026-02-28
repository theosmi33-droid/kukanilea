import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import re
from datetime import datetime



def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    monkeypatch.setenv("MAIL_MODE", "outbox")
    monkeypatch.setenv("DEV_LOCAL_EMAIL_CODES", "1")
    app = create_app()
    app.config["TESTING"] = True
    return app


def _set_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"
    return "test-csrf"


def test_forgot_shows_local_code_in_dev_mode_and_reset_works(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("alice", hash_password("old-pass"), now)
        auth_db.upsert_membership("alice", "KUKANILEA", "ADMIN", now)

    csrf = _set_csrf(client)
    r1 = client.post("/forgot", data={"username": "alice", "csrf_token": csrf})
    assert r1.status_code == 200
    body1 = r1.get_data(as_text=True)
    assert "DEV Local Code:" in body1

    m = re.search(r"DEV Local Code:\s*</strong>\s*(\d{6})", body1)
    assert m, body1
    code = m.group(1)

    csrf = _set_csrf(client)
    r2 = client.post(
        "/reset-code",
        data={
            "username": "alice",
            "code": code,
            "password": "new-pass",
            "password_confirm": "new-pass",
            "csrf_token": csrf,
        },
    )
    assert r2.status_code == 200
    assert "Passwort wurde aktualisiert" in r2.get_data(as_text=True)

    csrf = _set_csrf(client)
    r3 = client.post(
        "/login",
        data={"username": "alice", "password": "new-pass", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r3.status_code in (301, 302)
