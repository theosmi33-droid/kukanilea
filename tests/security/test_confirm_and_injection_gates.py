from __future__ import annotations

import pytest


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
        ("/admin/settings/profile", {"language": "de", "timezone": "Europe/Berlin", "confirm": "YES"}),
        ("/admin/settings/users/disable", {"username": "other-admin", "confirm": "YES"}),
        ("/admin/settings/backup/run", {"confirm": "YES"}),
        ("/admin/settings/users/create", {"username": "new-admin", "password": "pw", "tenant_id": "KUKANILEA", "confirm": "YES"}),
        ("/admin/settings/users/update", {"username": "other-admin", "tenant_id": "KUKANILEA", "role": "manager", "confirm": "YES"}),
        ("/admin/settings/system", {"language": "de", "timezone": "Europe/Berlin", "backup_interval": "daily", "log_level": "INFO", "confirm": "YES"}),
        ("/admin/settings/branding", {"app_name": "KUKANILEA", "primary_color": "#2563eb", "footer_text": "x", "confirm": "YES"}),
        ("/admin/settings/license/upload", {"license_json": "{}", "confirm": "YES"}),
        ("/admin/settings/backup/restore", {"backup_name": "missing.bak", "confirm": "YES"}),
        ("/admin/settings/mesh/connect", {"peer_ip": "localhost", "peer_port": "5051", "confirm": "YES"}),
        ("/admin/settings/mesh/rotate-key", {"confirm": "YES"}),
    ],
)
def test_additional_critical_write_routes_require_confirm_gate(admin_client, route: str, payload: dict[str, str], monkeypatch):
    _, client = admin_client
    if route == "/admin/settings/mesh/connect":
        import app.routes.admin_tenants as admin_routes

        monkeypatch.setattr(admin_routes.MeshNetworkManager, "initiate_handshake", lambda *_args, **_kwargs: True)
    response = client.post(route, data=payload)
    if route == "/admin/settings/backup/restore":
        assert response.status_code == 500
        return
    if route == "/admin/settings/license/upload":
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_license"
        return
    assert response.status_code in {302, 303}


@pytest.mark.parametrize(
    "route,payload",
    [
        ("/admin/settings/profile", {"language": "de", "timezone": "Europe/Berlin"}),
        ("/admin/settings/users/disable", {"username": "other-admin"}),
        ("/admin/settings/backup/run", {}),
        ("/admin/settings/users/create", {"username": "new-admin", "password": "pw", "tenant_id": "KUKANILEA"}),
        ("/admin/settings/users/update", {"username": "other-admin", "tenant_id": "KUKANILEA", "role": "manager"}),
        ("/admin/settings/system", {"language": "de", "timezone": "Europe/Berlin", "backup_interval": "daily", "log_level": "INFO"}),
        ("/admin/settings/branding", {"app_name": "KUKANILEA", "primary_color": "#2563eb", "footer_text": "x"}),
        ("/admin/settings/license/upload", {"license_json": "{}"}),
        ("/admin/settings/backup/restore", {"backup_name": "missing.bak"}),
        ("/admin/settings/mesh/connect", {"peer_ip": "localhost", "peer_port": "5051"}),
        ("/admin/settings/mesh/rotate-key", {}),
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
    assert "script-src-attr 'none'" in csp
    assert "script-src 'self' 'nonce-" in csp
    assert "unsafe-eval" not in csp
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "upgrade-insecure-requests" in csp
    assert "worker-src 'self'" in csp
    assert "blob:" not in csp
    assert "object-src 'self'" not in csp



def test_confirm_gate_matrix_covers_critical_admin_routes():
    from app.security.gates import CRITICAL_CONFIRM_GATE_BY_ROUTE

    expected = {
        "/admin/settings/profile",
        "/admin/settings/users/create",
        "/admin/settings/users/update",
        "/admin/settings/users/disable",
        "/admin/settings/users/delete",
        "/admin/settings/tenants/add",
        "/admin/settings/license/upload",
        "/admin/settings/system",
        "/admin/settings/branding",
        "/admin/settings/backup/run",
        "/admin/settings/backup/restore",
        "/admin/settings/mesh/connect",
        "/admin/settings/mesh/rotate-key",
    }
    assert expected.issubset(set(CRITICAL_CONFIRM_GATE_BY_ROUTE))
