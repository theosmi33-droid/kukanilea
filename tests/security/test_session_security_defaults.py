from __future__ import annotations

from app import create_app
from app.config import Config
from app.security.session_policy import resolve_session_cookie_policy


def _set_minimum_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("KUKANILEA_SECRET", "test-secret")
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")


def test_production_session_defaults_are_secure(monkeypatch, tmp_path):
    monkeypatch.setenv("KUKANILEA_ENV", "production")
    _set_minimum_paths(monkeypatch, tmp_path)

    app = create_app()

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_NAME"].startswith("__Host-")
    assert app.config["SESSION_COOKIE_DOMAIN"] is None
    assert app.config["SESSION_COOKIE_PATH"] == "/"


def test_production_session_hardening_ignores_insecure_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("KUKANILEA_ENV", "production")
    _set_minimum_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(Config, "SESSION_COOKIE_HTTPONLY", False, raising=False)
    monkeypatch.setattr(Config, "SESSION_COOKIE_SAMESITE", "None", raising=False)
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", False, raising=False)

    app = create_app()

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_development_session_defaults_allow_non_secure_cookie(monkeypatch, tmp_path):
    monkeypatch.setenv("KUKANILEA_ENV", "development")
    _set_minimum_paths(monkeypatch, tmp_path)

    app = create_app()

    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["SESSION_COOKIE_NAME"] == "kukanilea_session"


def test_development_session_secure_override_is_normalized(monkeypatch, tmp_path):
    monkeypatch.setenv("KUKANILEA_ENV", "development")
    _set_minimum_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", "TRUE", raising=False)

    app = create_app()

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_NAME"].startswith("__Host-")
    assert app.config["SESSION_COOKIE_DOMAIN"] is None
    assert app.config["SESSION_COOKIE_PATH"] == "/"


def test_test_environment_defaults_to_non_secure_cookie_for_local_pytest(monkeypatch, tmp_path):
    monkeypatch.setenv("KUKANILEA_ENV", "test")
    _set_minimum_paths(monkeypatch, tmp_path)

    app = create_app()

    assert app.config["SESSION_COOKIE_SECURE"] is False
    assert app.config["SESSION_COOKIE_NAME"] == "kukanilea_session"


def test_unknown_environment_falls_back_to_secure_cookie_policy():
    policy = resolve_session_cookie_policy("qa-preview", configured_secure=False)
    assert policy["SESSION_COOKIE_SECURE"] is True
    assert policy["SESSION_COOKIE_NAME"].startswith("__Host-")


def test_test_policy_honors_explicit_secure_override_for_https_ci():
    policy = resolve_session_cookie_policy("testing", configured_secure="1")
    assert policy["SESSION_COOKIE_SECURE"] is True
    assert policy["SESSION_COOKIE_NAME"].startswith("__Host-")
