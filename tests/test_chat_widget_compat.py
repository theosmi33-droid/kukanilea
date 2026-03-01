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
    app = create_app()
    app.config["TESTING"] = True
    return app


def test_api_chat_accepts_message_field_and_returns_response_alias(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    import app.web as web

    monkeypatch.setattr(web, "agent_answer", lambda msg: {"ok": True, "text": f"echo:{msg}"})

    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    resp = client.post(
        "/api/chat",
        json={"message": "hallo"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["text"] == "echo:hallo"
    assert data["response"] == "echo:hallo"


def test_layout_contains_light_theme_and_chat_msg_contract(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "classList.add('light')" in html
    assert "JSON.stringify({ msg: text })" in html
    assert "data.text || data.response" in html
