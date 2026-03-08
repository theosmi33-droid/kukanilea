from __future__ import annotations

from tests.test_dashboard_summary_health_widgets import _auth_client, _make_app


def test_visualizer_template_uses_human_state_copy(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get('/visualizer')
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert 'Noch keine Vorschau verfügbar' in body
    assert 'Mehr anzeigen' in body
    assert 'Erneut laden' in body
    assert 'Dokument konnte gerade nicht gerendert werden' in body
