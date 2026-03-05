from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import create_app
from app.auth import hash_password, login_user
from app.config import Config
from app.security.http_policy import is_allowed_redirect_target


def _make_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KUKANILEA_SECRET", "test-secret")
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", "2024-01-01T00:00:00Z")
        auth_db.upsert_user("admin", hash_password("admin"), "2024-01-01T00:00:00Z")
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", "2024-01-01T00:00:00Z")
    return app


def test_cors_allowlist_blocks_unknown_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_CORS_ORIGINS", "https://trusted.example")
    monkeypatch.delenv("KUKANILEA_DEBUG_STRESS", raising=False)
    app = _make_app(tmp_path, monkeypatch)
    c = app.test_client()

    denied = c.open("/api/ping", method="OPTIONS", headers={"Origin": "https://evil.example"})
    assert denied.status_code == 403

    allowed = c.open("/api/ping", method="OPTIONS", headers={"Origin": "https://trusted.example"})
    assert allowed.status_code in {200, 204, 405}


def test_redirect_allowlist_rejects_external_target():
    assert is_allowed_redirect_target("/dashboard", {"localhost:5051"})
    assert not is_allowed_redirect_target("https://evil.example/phish", {"localhost:5051"})


def test_no_raw_errors_exposed_to_client(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    # Remove extension to force controlled internal error path.
    del app.extensions["auth_db"]
    resp = c.get("/api/outbound/status")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_rate_limit_on_sensitive_endpoint(tmp_path, monkeypatch):
    from app.rate_limit import RateLimiter

    limiter = RateLimiter(limit=2, window_s=60)
    assert limiter.allow("client-a")
    assert limiter.allow("client-a")
    assert not limiter.allow("client-a")

    api_source = Path("app/api.py").read_text()
    assert "@chat_limiter.limit_required\ndef intake_execute" in api_source
    assert "@search_limiter.limit_required\ndef outbound_status" in api_source


def test_session_fixation_rotates_session(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with app.test_request_context("/"):
        from flask import session

        session["csrf_token"] = "keep-me"
        login_user("admin", "ADMIN", "KUKANILEA")
        assert session.get("session_sid")
        assert session.get("session_issued_at")


def test_server_side_permission_checks_enforced(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    c = app.test_client()

    anonymous = c.post("/api/intake/execute", json={})
    assert anonymous.status_code == 401

    with c.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "READONLY"
        sess["tenant_id"] = "KUKANILEA"
    forbidden = c.get("/api/outbound/status")
    assert forbidden.status_code == 403


def test_storage_acl_isolation_denies_outside_paths(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    from app import web

    outside = tmp_path.parent / "outside.sqlite3"
    assert web._is_allowlisted_path(app.config["IMPORT_ROOT"])
    assert not web._is_allowlisted_path(outside)


def test_dependency_audit_gate_script_exists_and_has_deterministic_codes():
    script = Path("scripts/ops/security_gate.sh")
    assert script.exists()
    body = script.read_text()
    for code in ["exit 0", "exit 10", "exit 20", "exit 30"]:
        assert code in body


def test_no_debug_prints_in_runtime_paths():
    for rel in ["app/api.py", "app/auth.py", "app/security/session_manager.py"]:
        assert "\nprint(" not in Path(rel).read_text()


def test_secrets_never_reflected_in_error_payload(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    os.environ["TOP_SECRET_TEST"] = "dont-leak-me"
    del app.extensions["auth_db"]
    resp = c.get("/api/outbound/status")
    assert "dont-leak-me" not in resp.get_data(as_text=True)
