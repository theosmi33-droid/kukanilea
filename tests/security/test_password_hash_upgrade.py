from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from app.auth import hash_password, verify_password
from tests.time_utils import utc_now_iso


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


def test_hash_password_uses_modern_kdf():
    hashed = hash_password("secret-value")
    assert hashed.startswith("scrypt:")


def test_verify_password_accepts_legacy_sha256():
    legacy = hashlib.sha256(b"secret-value").hexdigest()
    valid, needs_rehash = verify_password(legacy, "secret-value")
    assert valid is True
    assert needs_rehash is True


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


def test_login_upgrades_legacy_hash_to_kdf(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        legacy = hashlib.sha256(b"legacy-pass").hexdigest()
        auth_db.upsert_user("legacy", legacy, now)
        auth_db.upsert_membership("legacy", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    csrf = _extract_csrf(client.get("/login").get_data(as_text=True))
    response = client.post(
        "/login",
        data={"username": "legacy", "password": "legacy-pass", "csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        user = auth_db.get_user("legacy")
        assert user is not None
        assert not re.fullmatch(r"[0-9a-f]{64}", user.password_hash or "")
        assert user.password_hash.startswith("scrypt:")

