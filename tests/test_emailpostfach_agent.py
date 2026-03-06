from __future__ import annotations

from app.db import AuthDB
from app.modules.mail.postfach import EmailpostfachService, ProviderAuthError, ProviderNetworkError, StubInboxProvider
from tests.time_utils import utc_now_iso


def _init_auth_db(db_path) -> AuthDB:
    auth_db = AuthDB(db_path)
    auth_db.init()
    now = utc_now_iso()
    from app.auth import hash_password

    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user("admin", hash_password("admin"), now)
    auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    return auth_db


def _client(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        _init_auth_db(app.config["AUTH_DB"])

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "test-csrf"
    return client


def test_unit_template_fallback_and_confirm_gate(tmp_path):
    auth_db = _init_auth_db(tmp_path / "auth.sqlite3")
    service = EmailpostfachService(db_path=str(auth_db.path))

    draft = service.create_draft(
        tenant_id="KUKANILEA",
        actor="admin",
        message={"subject": "Dringend: Bitte melden", "from": "kunde@example.com"},
        use_llm=False,
    )

    assert draft["generator"] == "template"
    assert draft["confirm_required"] is True
    assert draft["send_allowed"] is False


def test_unit_ingest_summary_and_send_audit(tmp_path):
    auth_db = _init_auth_db(tmp_path / "auth.sqlite3")
    service = EmailpostfachService(db_path=str(auth_db.path))

    ingest = service.ingest(tenant_id="KUKANILEA", provider_name="imap_stub", actor="admin")
    assert ingest["inserted"] == 1

    summary = service.summary(tenant_id="KUKANILEA")
    assert summary["metrics"]["unread_count"] == 1
    assert "last_sync" in summary

    draft = service.create_draft(
        tenant_id="KUKANILEA",
        actor="admin",
        message={"subject": "Angebot", "from": "kunde@example.com"},
    )
    blocked = service.send_draft(tenant_id="KUKANILEA", actor="admin", draft_id=draft["id"], confirm=False)
    assert blocked["status"] == "blocked"

    sent = service.send_draft(tenant_id="KUKANILEA", actor="admin", draft_id=draft["id"], confirm=True)
    assert sent["status"] == "sent"


def test_unit_ingest_failure_auth_and_network(tmp_path):
    auth_db = _init_auth_db(tmp_path / "auth.sqlite3")

    def provider_factory(name: str):
        if name == "auth_fail":
            return StubInboxProvider(mode="auth_fail")
        return StubInboxProvider(mode="network_fail")

    service = EmailpostfachService(db_path=str(auth_db.path), inbox_provider_factory=provider_factory)

    try:
        service.ingest(tenant_id="KUKANILEA", provider_name="auth_fail", actor="admin")
        raise AssertionError("expected ProviderAuthError")
    except ProviderAuthError:
        pass

    try:
        service.ingest(tenant_id="KUKANILEA", provider_name="network_fail", actor="admin")
        raise AssertionError("expected ProviderNetworkError")
    except ProviderNetworkError:
        pass


def test_integration_emailpostfach_api_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"X-CSRF-Token": "test-csrf"}

    ingest = client.post("/api/emailpostfach/ingest", json={"provider": "imap_stub", "actor": "admin"}, headers=headers)
    assert ingest.status_code == 200
    assert ingest.get_json()["result"]["inserted"] == 1

    summary = client.get("/api/emailpostfach/summary")
    assert summary.status_code == 200
    summary_payload = summary.get_json()
    assert summary_payload["metrics"]["unread_count"] >= 1
    assert "follow_ups_due" in summary_payload["metrics"]
    assert "last_sync" in summary_payload

    draft_resp = client.post(
        "/api/emailpostfach/draft/generate",
        json={"message": {"subject": "Termin", "from": "kunde@example.com"}, "actor": "admin"},
        headers=headers,
    )
    assert draft_resp.status_code == 200
    draft_id = draft_resp.get_json()["draft"]["id"]

    edit = client.post(
        f"/api/emailpostfach/draft/{draft_id}/edit",
        json={"subject": "Aktualisiert", "body": "Neue Nachricht", "actor": "admin"},
        headers=headers,
    )
    assert edit.status_code == 200

    blocked_send = client.post(
        f"/api/emailpostfach/draft/{draft_id}/send",
        json={"confirm": "no", "actor": "admin"},
        headers=headers,
    )
    assert blocked_send.status_code == 409

    send = client.post(
        f"/api/emailpostfach/draft/{draft_id}/send",
        json={"confirm": "yes", "actor": "admin"},
        headers=headers,
    )
    assert send.status_code == 200


def test_integration_ingest_failure_responses(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"X-CSRF-Token": "test-csrf"}

    auth_fail = client.post("/api/emailpostfach/ingest", json={"provider": "auth_fail"}, headers=headers)
    network_fail = client.post("/api/emailpostfach/ingest", json={"provider": "network_fail"}, headers=headers)

    assert auth_fail.status_code == 401
    assert auth_fail.get_json()["error"] == "provider_auth_failed"
    assert network_fail.status_code == 503
    assert network_fail.get_json()["error"] == "provider_network_unavailable"
