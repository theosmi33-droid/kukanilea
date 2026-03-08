import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from tests.time_utils import utc_now_iso


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
    # CSP hardening moved compact chat logic into static/js/layout-shell.js.
    assert 'src="/static/js/layout-shell.js"' in html
    assert "fetch('/api/chat/compact'" not in html
    assert "id=\"chat-plan\"" in html
    assert "id=\"chat-actions\"" in html

    shell_js = Path(__file__).resolve().parents[1] / "static" / "js" / "layout-shell.js"
    source = shell_js.read_text(encoding="utf-8")
    assert "fetch('/api/chat/compact'" in source
    assert "pending_id: chatPendingId" in source
    assert "data.text || data.response" in source

    runtime_shell_js = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "layout-shell.js"
    assert runtime_shell_js.exists()
    runtime_source = runtime_shell_js.read_text(encoding="utf-8")
    assert "fetch('/api/chat/compact'" in runtime_source


def test_confirm_dialog_component_uses_human_friendly_copy():
    from pathlib import Path

    floating_chat = Path("app/templates/partials/floating_chat.html").read_text(encoding="utf-8")
    template = Path("app/templates/components/confirm_dialog.html").read_text(encoding="utf-8")
    ui_feedback = Path("app/static/js/ui-feedback.js").read_text(encoding="utf-8")

    assert "id=\"floating-chat-confirm-risk\"" in floating_chat
    assert "id=\"floating-chat-confirm-preview\"" in floating_chat
    assert "Freigeben &amp; ausführen" in floating_chat
    assert "Sicherheitsabfrage" in template
    assert "Nicht ausführen" in template
    assert "Freigeben" in template
    assert "normalizeConfirmMessage" in ui_feedback


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
    assert len(body["pending_approvals"]) == 1
    assert body["pending_approvals"][0]["pending_id"] == body["pending_id"]

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
    assert confirmed["pending_approvals"] == []
    assert "ausgeführt" in confirmed["status"].lower()


def test_compact_chat_maintains_pending_approvals_queue(tmp_path, monkeypatch):
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

    first = client.post(
        "/api/chat/compact",
        json={"message": "Bitte sende den Report", "current_context": "/dashboard"},
        headers={"X-CSRF-Token": "csrf-test"},
    ).get_json()
    second = client.post(
        "/api/chat/compact",
        json={"message": "Bitte erstelle Aufgabe für Follow-up", "current_context": "/dashboard"},
        headers={"X-CSRF-Token": "csrf-test"},
    ).get_json()

    assert first["pending_id"]
    assert second["pending_id"]
    assert len(second["pending_approvals"]) == 2

    listing = client.get(
        "/api/chat/compact?pending=1",
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert listing.status_code == 200
    listed = listing.get_json()
    assert listed["ok"] is True
    assert len(listed["pending_approvals"]) == 2


def test_widget_pending_helpers_keep_contract_shape():
    from app.widget_pending import (
        compact_pending_actions,
        mark_actions_confirm_required,
        serialize_pending_approvals,
        widget_requires_confirm,
    )

    actions = [{"type": "send_message", "label": "Senden"}]
    marked = mark_actions_confirm_required(actions)

    assert marked[0]["requires_confirm"] is True
    assert marked[0]["confirm_required"] is True
    assert widget_requires_confirm(marked) is True

    compact = compact_pending_actions(marked)
    assert compact == [{"type": "send_message", "label": "Senden", "confirm_required": True}]

    pending = serialize_pending_approvals([
        {
            "id": "abc",
            "actions": compact,
            "current_context": "/messenger",
            "confirm_prompt": "Bestätigen",
        }
    ])
    assert pending == [
        {
            "pending_id": "abc",
            "current_context": "/messenger",
            "confirm_prompt": "Bestätigen",
            "action_count": 1,
        }
    ]
