import sys
from pathlib import Path
from tests.time_utils import utc_now_iso

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_standard_request_detector_handles_common_messages():
    from app.ai.intent_analyzer import detect_standard_request

    assert detect_standard_request("Hallo") == "greeting"
    assert detect_standard_request("test") == "self_test"
    assert detect_standard_request("Funktionierst du?") == "self_test"



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
        now = utc_now_iso()
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
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "classList.add('light')" in html
    assert "JSON.stringify({ msg: text })" in html
    assert "data.text || data.response" in html


def test_compact_chat_write_intent_requires_confirm_and_executes_after_yes(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    import app.web as web

    monkeypatch.setattr(web, "agent_answer", lambda *_args, **_kwargs: {"ok": True, "text": "bereit", "actions": []})

    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    resp = client.post(
        "/api/chat/compact",
        json={"message": "Bitte sende die Nachricht an den Kunden", "current_context": "/messenger"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["requires_confirm"] is True
    assert body["pending_id"]

    yes = client.post(
        "/api/chat/compact",
        json={"confirm": True, "pending_id": body["pending_id"], "current_context": "/messenger"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert yes.status_code == 200
    confirmed = yes.get_json()
    assert confirmed["ok"] is True
    assert confirmed["requires_confirm"] is False
    assert confirmed["pending_id"] == ""
    assert "ausgeführt" in confirmed["status"].lower()
