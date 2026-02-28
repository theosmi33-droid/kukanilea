import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from datetime import datetime



def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    monkeypatch.setenv("MAIL_MODE", "smtp")
    monkeypatch.setenv("DEV_LOCAL_EMAIL_CODES", "0")
    app = create_app()
    app.config["TESTING"] = True
    return app


def _set_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-csrf"
    return "test-csrf"


def test_forgot_blind_success_without_dev_mode(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("bob", hash_password("secret"), now)
        auth_db.upsert_membership("bob", "KUKANILEA", "ADMIN", now)

    csrf = _set_csrf(client)
    resp = client.post("/forgot", data={"username": "bob", "csrf_token": csrf})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Wenn ein passender Account existiert, wurde ein Code erzeugt." in body
    assert "DEV Local Code:" not in body
