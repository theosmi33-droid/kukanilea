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


class _FakeResult:
    def __init__(self, *, text, actions=None, suggestions=None, ok=True):
        self.text = text
        self.actions = actions or []
        self.suggestions = suggestions or []
        self.ok = ok


class _FakeOrchestrator:
    def __init__(self, result):
        self.result = result

    def handle(self, _message, _context):
        return self.result


def _seed_dev(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)


def _login(client):
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"


def test_compact_chat_confirm_required_flow(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_dev(app)
    _login(client)

    import app.web as web

    fake = _FakeResult(
        text="Ich habe eine schreibende Aktion vorbereitet.",
        actions=[{"type": "memory_store", "label": "Notiz speichern"}],
        suggestions=["hilfe"],
        ok=True,
    )
    monkeypatch.setattr(web, "ORCHESTRATOR", _FakeOrchestrator(fake))

    first = client.post(
        "/api/chat/compact",
        json={"message": "speichere notiz", "current_context": "/dashboard"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert first.status_code == 200
    data = first.get_json()
    assert data["requires_confirm"] is True
    assert data["pending_id"]
    assert data["actions"][0]["requires_confirm"] is True

    second = client.post(
        "/api/chat/compact",
        json={"confirm": True, "pending_id": data["pending_id"], "current_context": "/dashboard"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert second.status_code == 200
    cdata = second.get_json()
    assert cdata["ok"] is True
    assert "executed_actions" in cdata
    assert cdata["executed_actions"][0]["status"] == "approved"


def test_compact_chat_history_includes_context_tagged_message(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_dev(app)
    _login(client)

    import app.web as web

    fake = _FakeResult(text="Antwort verfügbar.", actions=[], suggestions=["hilfe"], ok=True)
    monkeypatch.setattr(web, "ORCHESTRATOR", _FakeOrchestrator(fake))

    send = client.post(
        "/api/chat/compact",
        json={"message": "status", "current_context": "/upload"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert send.status_code == 200

    history = client.get("/api/chat/compact?history=1&limit=20")
    assert history.status_code == 200
    hdata = history.get_json()
    assert hdata["ok"] is True
    messages = hdata["messages"]
    assert any("[/upload] status" in item["message"] for item in messages)
    assert any(item["message"] == "Antwort verfügbar." for item in messages)
