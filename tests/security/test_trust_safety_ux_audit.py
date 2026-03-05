from __future__ import annotations

from app import create_app
from app.config import Config
from tests.time_utils import utc_now_iso


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_DEBUG_STRESS", "1")
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    app = create_app()
    app.config["TESTING"] = True
    return app


def _bootstrap_admin(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("auditor", hash_password("auditor"), now)
        auth_db.upsert_membership("auditor", "KUKANILEA", "ADMIN", now)


def _set_session(client, *, role: str):
    with client.session_transaction() as sess:
        sess["user"] = "auditor"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-audit"


def test_trust_safety_ux_audit_runs_2200_plus_actions(tmp_path, monkeypatch):
    """Stress-audit confirm gates, destructive-action friction, and permission cues."""
    app = _make_app(tmp_path, monkeypatch)
    _bootstrap_admin(app)
    client = app.test_client()

    actions = 0

    # Permission cue: anonymous users are redirected to login.
    anonymous = client.get("/settings", follow_redirects=False)
    actions += 1
    assert anonymous.status_code in {301, 302}
    assert "/login" in anonymous.headers["Location"]

    # Permission cue: authenticated non-admin users are forbidden.
    _set_session(client, role="USER")
    forbidden = client.get("/settings")
    actions += 1
    assert forbidden.status_code == 403

    # Admin session for critical workflow checks.
    _set_session(client, role="ADMIN")

    # Confirm-friction cues are present in Settings UI for destructive actions.
    settings = client.get("/settings")
    actions += 1
    page = settings.get_data(as_text=True)
    assert settings.status_code == 200
    assert "name=\"confirm\"" in page
    assert "placeholder=\"CONFIRM\"" in page
    assert "confirmRisk(form)" in page
    assert "Riskante Aktion ausführen?" in page

    # Confirm gate: write-like AI skill cannot execute without explicit confirm.
    denied = client.post(
        "/api/ai/execute",
        json={"skill": "create_task", "payload": {"title": "unsafe"}, "confirm": False},
        headers={"X-CSRF-Token": "csrf-audit"},
    )
    actions += 1
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "confirm_required"

    # Positive control with explicit confirmation.
    allowed = client.post(
        "/api/ai/execute",
        json={"skill": "create_task", "payload": {"title": "safe"}, "confirm": True},
        headers={"X-CSRF-Token": "csrf-audit"},
    )
    actions += 1
    assert allowed.status_code == 200
    assert allowed.get_json()["ok"] is True

    # Execute >=2200 actions across critical trust/safety UX surfaces.
    for _ in range(730):
        res = client.get("/settings")
        actions += 1
        assert res.status_code == 200

    for _ in range(730):
        res = client.post(
            "/api/ai/execute",
            json={"skill": "create_task", "payload": {"title": "blocked"}, "confirm": False},
            headers={"X-CSRF-Token": "csrf-audit"},
        )
        actions += 1
        assert res.status_code == 403

    for _ in range(740):
        res = client.post(
            "/api/chat/compact",
            json={"message": "please create task now", "current_context": "/messenger"},
            headers={"X-CSRF-Token": "csrf-audit"},
        )
        actions += 1
        assert res.status_code == 200
        body = res.get_json()
        assert body["requires_confirm"] is True

    assert actions >= 2200
