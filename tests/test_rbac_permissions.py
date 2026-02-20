from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import create_app
from app.auth import hash_password
from app.config import Config


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "TENANT_DEFAULT", "KUKANILEA")
    monkeypatch.setattr(Config, "TENANT_NAME", "KUKANILEA")
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        READ_ONLY=False,
        TENANT_FIXED_TEST_ENFORCE=True,
    )
    return app


def _seed_user(app, *, username: str, role: str, email: str = "") -> None:
    auth_db = app.extensions["auth_db"]
    now = datetime.now(timezone.utc).isoformat()
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user(username, hash_password("pw123456"), now)
    auth_db.upsert_membership(username, "KUKANILEA", "OPERATOR", now)
    if email:
        user = auth_db.get_user(username)
        assert user is not None
    auth_db.set_user_roles(username, [role], actor_roles=["DEV"])


def _login(client, username: str, role: str) -> None:
    with client.session_transaction() as sess:
        sess["user"] = username
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_permissions_manager_denies_office(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    _seed_user(app, username="owner", role="OWNER_ADMIN")
    _seed_user(app, username="office", role="OFFICE")
    client = app.test_client()
    _login(client, "office", "OPERATOR")
    res = client.get("/settings/permissions")
    assert res.status_code == 403


def test_permissions_manager_allows_owner_admin(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    _seed_user(app, username="owner", role="OWNER_ADMIN")
    client = app.test_client()
    _login(client, "owner", "ADMIN")
    res = client.get("/settings/permissions")
    assert res.status_code == 200
    assert b"Berechtigungen" in res.data


def test_dev_update_is_dev_only(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    _seed_user(app, username="owner", role="OWNER_ADMIN")
    _seed_user(app, username="dev", role="DEV")
    client = app.test_client()

    _login(client, "owner", "ADMIN")
    denied = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert denied.status_code == 403

    _login(client, "dev", "DEV")
    allowed = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert allowed.status_code == 200
    assert b"DEV Update Center" in allowed.data


def test_owner_admin_uniqueness_enforced(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    auth_db = app.extensions["auth_db"]
    now = datetime.now(timezone.utc).isoformat()
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user("owner", hash_password("pw123456"), now)
    auth_db.upsert_membership("owner", "KUKANILEA", "ADMIN", now)
    auth_db.set_user_roles("owner", ["OWNER_ADMIN"], actor_roles=["DEV"])
    auth_db.upsert_user("other", hash_password("pw123456"), now)
    auth_db.upsert_membership("other", "KUKANILEA", "OPERATOR", now)
    auth_db.set_user_roles("other", ["OFFICE"], actor_roles=["DEV"])

    with pytest.raises(ValueError):
        auth_db.set_user_roles(
            "other",
            ["OWNER_ADMIN"],
            actor_roles=["OFFICE"],
        )
