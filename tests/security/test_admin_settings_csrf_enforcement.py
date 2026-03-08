from __future__ import annotations

import pytest

from tests.test_settings_governance import _make_app


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/admin/settings/profile", {"language": "de", "timezone": "Europe/Berlin"}),
        ("/admin/settings/users/create", {"username": "user-a", "password": "pw", "tenant_id": "KUKANILEA", "role": "mitarbeiter", "confirm": "CONFIRM"}),
        ("/admin/settings/users/update", {"username": "admin", "tenant_id": "KUKANILEA", "role": "admin", "confirm": "CONFIRM"}),
        ("/admin/settings/users/disable", {"username": "admin2", "confirm": "CONFIRM"}),
        ("/admin/settings/users/delete", {"username": "admin2", "confirm": "CONFIRM"}),
        ("/admin/settings/tenants/add", {"name": "Tenant X", "db_path": "/tmp/missing.sqlite3", "confirm": "CONFIRM"}),
        ("/admin/context/switch", {"tenant_id": "KUKANILEA", "confirm": "CONFIRM"}),
        ("/admin/settings/license/upload", {"license_json": "{\"plan\":\"ENTERPRISE\"}", "confirm": "CONFIRM"}),
        ("/admin/settings/system", {"language": "de", "timezone": "Europe/Berlin", "confirm": "CONFIRM"}),
        ("/admin/settings/branding", {"app_name": "KUKANILEA", "primary_color": "#ffffff", "confirm": "CONFIRM"}),
        ("/admin/settings/backup/run", {"confirm": "CONFIRM"}),
        ("/admin/settings/backup/restore", {"backup_name": "missing.bak", "confirm": "CONFIRM"}),
        ("/admin/settings/mesh/connect", {"peer_ip": "127.0.0.1", "peer_port": "5051", "confirm": "CONFIRM"}),
        ("/admin/settings/mesh/rotate-key", {"confirm": "CONFIRM"}),
    ],
)
def test_admin_settings_post_routes_block_without_csrf(tmp_path, monkeypatch, path: str, payload: dict[str, str]):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    response = client.post(path, data=payload)
    assert response.status_code == 403


def test_admin_settings_post_routes_block_with_wrong_csrf(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    response = client.post(
        "/admin/settings/system",
        data={
            "language": "en",
            "timezone": "UTC",
            "confirm": "CONFIRM",
            "csrf_token": "wrong-token",
        },
    )
    assert response.status_code == 403


def test_admin_settings_profile_accepts_valid_csrf(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"

    response = client.post(
        "/admin/settings/profile",
        data={
            "language": "en",
            "timezone": "UTC",
            "confirm": "CONFIRM",
            "csrf_token": "csrf-test",
        },
    )
    assert response.status_code in {302, 303}

