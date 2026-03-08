from __future__ import annotations

from tests.domain.aufgaben.test_actions_api import _auth_client, _make_app


def test_settings_action_catalog_reports_admin_permission(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app, role="ADMIN", username="admin")

    response = client.get("/api/settings/actions")
    assert response.status_code == 200

    actions = {item["name"]: item for item in response.get_json()["actions"]}
    assert actions["setting.update"]["permission"] == "admin"
    assert actions["setting.update"]["confirm_required"] is False
