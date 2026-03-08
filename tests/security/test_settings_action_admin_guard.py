from __future__ import annotations

from tests.domain.aufgaben.test_actions_api import _auth_client, _make_app


def test_settings_update_rejects_operator_even_with_approval_token(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    operator_client = _auth_client(app, role="OPERATOR", username="operator")

    response = operator_client.post(
        "/api/settings/actions/setting.update",
        json={"key": "language", "value": "en", "approval_token": "fake-token"},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["error"]["code"] == "forbidden"
