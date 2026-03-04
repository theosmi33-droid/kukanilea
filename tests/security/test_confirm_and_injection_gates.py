from __future__ import annotations

from tests.time_utils import utc_now_iso

from pathlib import Path

import pytest


@pytest.fixture()
def admin_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app
    from app.auth import hash_password
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
        auth_db.upsert_user("other-admin", hash_password("admin"), now)
        auth_db.upsert_membership("other-admin", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    return app, client


@pytest.mark.parametrize("confirm_value", ["YES", "yes", "true", "1", "CONFIRM"])
def test_write_routes_require_confirm_gate_accepts_expected_tokens(admin_client, confirm_value: str):
    _, client = admin_client
    response = client.post(
        "/admin/settings/users/delete",
        data={"username": "other-admin", "confirm": confirm_value},
    )
    assert response.status_code in {302, 303}
    assert response.headers["Location"].endswith("/admin/settings?section=users")


@pytest.mark.parametrize("confirm_value", ["", "no", "0", "false", " y "])
def test_delete_user_rejects_invalid_confirm_tokens(admin_client, confirm_value: str):
    _, client = admin_client
    response = client.post(
        "/admin/settings/users/delete",
        data={"username": "other-admin", "confirm": confirm_value},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "confirm_required"


def test_delete_user_blocks_sql_pattern_in_confirm(admin_client):
    _, client = admin_client
    response = client.post(
        "/admin/settings/users/delete",
        data={"username": "other-admin", "confirm": "YES; DROP TABLE users; --"},
    )
    body = response.get_json()
    assert response.status_code == 400
    assert body["error"] == "injection_blocked"
    assert body["field"] == "confirm"


@pytest.mark.parametrize(
    ("route", "payload", "blocked_field"),
    [
        (
            "/admin/settings/users/create",
            {"username": "alice'; DROP TABLE users; --", "password": "pw", "tenant_id": "KUKANILEA", "confirm": "CONFIRM"},
            "username",
        ),
        (
            "/admin/settings/tenants/add",
            {"name": "KUKANILEA<script>alert(1)</script>", "db_path": "/tmp/core.sqlite3", "confirm": "CONFIRM"},
            "name",
        ),
        (
            "/admin/settings/mesh/connect",
            {"peer_ip": "javascript:alert(1)", "peer_port": "5051", "confirm": "CONFIRM"},
            "peer_ip",
        ),
    ],
)
def test_security_critical_routes_block_injection_payloads(admin_client, route: str, payload: dict[str, str], blocked_field: str):
    _, client = admin_client
    response = client.post(route, data=payload)
    body = response.get_json()
    assert response.status_code == 400
    assert body["error"] == "injection_blocked"
    assert body["field"] == blocked_field


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        ("/admin/settings/users/disable", {"username": "other-admin", "confirm": "YES"}),
        ("/admin/settings/backup/run", {"confirm": "YES"}),
        ("/admin/settings/users/create", {"username": "new-admin", "password": "pw", "tenant_id": "KUKANILEA", "confirm": "YES"}),
        ("/admin/settings/users/update", {"username": "other-admin", "tenant_id": "KUKANILEA", "role": "manager", "confirm": "YES"}),
        ("/admin/settings/system", {"language": "de", "timezone": "Europe/Berlin", "backup_interval": "daily", "log_level": "INFO", "confirm": "YES"}),
        ("/admin/settings/branding", {"app_name": "KUKANILEA", "primary_color": "#2563eb", "footer_text": "x", "confirm": "YES"}),
        ("/admin/settings/mesh/connect", {"peer_ip": "localhost", "peer_port": "5051", "confirm": "YES"}),
    ],
)
def test_additional_critical_write_routes_require_confirm_gate(admin_client, route: str, payload: dict[str, str], monkeypatch):
    _, client = admin_client
    if route == "/admin/settings/mesh/connect":
        import app.routes.admin_tenants as admin_routes

        monkeypatch.setattr(admin_routes.MeshNetworkManager, "initiate_handshake", lambda *_args, **_kwargs: True)
    response = client.post(route, data=payload)
    assert response.status_code in {302, 303}


@pytest.mark.parametrize(
    "route,payload",
    [
        ("/admin/settings/users/disable", {"username": "other-admin"}),
        ("/admin/settings/backup/run", {}),
        ("/admin/settings/users/create", {"username": "new-admin", "password": "pw", "tenant_id": "KUKANILEA"}),
        ("/admin/settings/users/update", {"username": "other-admin", "tenant_id": "KUKANILEA", "role": "manager"}),
        ("/admin/settings/system", {"language": "de", "timezone": "Europe/Berlin", "backup_interval": "daily", "log_level": "INFO"}),
        ("/admin/settings/branding", {"app_name": "KUKANILEA", "primary_color": "#2563eb", "footer_text": "x"}),
        ("/admin/settings/mesh/connect", {"peer_ip": "localhost", "peer_port": "5051"}),
    ],
)
def test_additional_critical_write_routes_reject_missing_confirm(admin_client, route: str, payload: dict[str, str]):
    _, client = admin_client
    response = client.post(route, data=payload)
    body = response.get_json()
    assert response.status_code == 400
    assert body["error"] == "confirm_required"


def test_security_headers_use_hardened_csp(admin_client):
    _, client = admin_client
    response = client.get("/admin/settings")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "connect-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'self'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "upgrade-insecure-requests" in csp
    assert "worker-src 'self'" in csp
    assert "blob:" not in csp
    assert "object-src 'self'" not in csp
