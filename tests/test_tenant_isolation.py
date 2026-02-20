from __future__ import annotations

import sqlite3

from flask import g

from app import create_app
from app.config import Config
from app.tenant.context import load_tenant_context


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "TENANT_DEFAULT", "KUKANILEA")
    monkeypatch.setattr(Config, "TENANT_NAME", "KUKANILEA")
    app = create_app()
    app.config.update(
        TESTING=True,
        TENANT_FIXED_TEST_ENFORCE=True,
        SECRET_KEY="test",
        READ_ONLY=False,
    )
    return app


def _login(client, *, role: str, tenant_id: str = "SPOOFED") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = tenant_id


def test_requires_tenant_context_when_not_public(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    tenant_db_path = app.config.get("TENANT_CONFIG_DB_PATH", app.config["CORE_DB"])
    con = sqlite3.connect(str(tenant_db_path))
    try:
        con.execute("DELETE FROM tenant_config WHERE id='fixed'")
        con.commit()
    finally:
        con.close()

    client = app.test_client()
    _login(client, role="ADMIN")
    res = client.get("/settings")
    assert res.status_code == 403


def test_tenant_context_is_set_and_overrides_session_tenant(
    monkeypatch, tmp_path
) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="ADMIN", tenant_id="TENANT_EVASION")

    res = client.get("/settings")
    assert res.status_code == 200

    with client.session_transaction() as sess:
        assert sess.get("tenant_id") == app.config["TENANT_DEFAULT"]

    with app.test_request_context("/settings"):
        response = app.preprocess_request()
        assert response is not None
        ctx = getattr(g, "tenant_ctx", None)
        assert ctx is not None
        assert ctx.tenant_id == app.config["TENANT_DEFAULT"]


def test_dev_can_edit_tenant_name_localhost_only(monkeypatch, tmp_path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="DEV")

    res = client.post(
        "/dev/tenant",
        data={"tenant_name": "ACME Handwerk"},
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert res.status_code == 200
    assert b"Tenant-Name aktualisiert" in res.data

    tenant_db_path = app.config.get("TENANT_CONFIG_DB_PATH", app.config["CORE_DB"])
    ctx = load_tenant_context(tenant_db_path)
    assert ctx is not None
    assert ctx.tenant_name == "ACME Handwerk"
    assert ctx.tenant_id == app.config["TENANT_DEFAULT"]


def test_dev_tenant_override_forbidden_for_remote_or_non_dev(
    monkeypatch, tmp_path
) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="DEV")

    remote = client.get("/dev/tenant", environ_overrides={"REMOTE_ADDR": "10.0.0.9"})
    assert remote.status_code == 403

    _login(client, role="ADMIN")
    non_dev = client.get("/dev/tenant")
    assert non_dev.status_code == 403
