from __future__ import annotations

from tests.time_utils import utc_now_iso


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


def _auth_client(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    return client


def test_dashboard_renders_speed_to_lead_and_health_strip(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/dashboard")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert 'id="speed-to-lead-widget"' in body
    assert 'id="speed-to-lead-cards"' in body
    assert 'id="system-health-strip"' in body
    assert 'id="health-strip-tools"' in body


def test_dashboard_widget_script_consumes_summary_and_health_contracts(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/dashboard")
    body = response.get_data(as_text=True)

    assert "const DASHBOARD_TOOLS =" in body
    assert "Promise.allSettled" in body
    assert "_fetchToolSummary" in body
    assert "_fetchJsonWithTimeout('/health'" in body
    assert "REFRESH_INTERVAL_MS" in body
    assert "healthRefreshInFlight" in body
    assert "matrixRefreshInFlight" in body


def test_dashboard_summary_contract_for_messenger_and_email_available(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    messenger = client.get("/api/messenger/summary")
    email = client.get("/api/email/summary")

    assert messenger.status_code == 200
    assert email.status_code == 200
    assert messenger.get_json().get("tool") == "messenger"
    assert email.get_json().get("tool") == "email"
