from __future__ import annotations

from tests.test_settings_governance import _make_app


def test_admin_settings_forms_include_hidden_csrf_fields(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.get("/admin/settings")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.count('name="csrf_token"') >= 12
    assert '<form method="post" action="/admin/settings/system"' in html
    assert '<form method="post" action="/admin/settings/backup/run"' in html
    assert '<form method="post" action="/admin/settings/license/upload"' in html
    assert '<form method="post" action="/admin/settings/mesh/connect"' in html

