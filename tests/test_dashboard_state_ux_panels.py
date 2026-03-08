from __future__ import annotations

from tests.test_dashboard_summary_health_widgets import _auth_client, _make_app


def _dashboard_html(tmp_path, monkeypatch) -> str:
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_dashboard_contains_state_slots_for_speed_to_lead_and_health(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert 'id="speed-to-lead-state"' in html
    assert 'id="health-strip-state"' in html


def test_dashboard_bootstrap_calls_loading_state_renderer(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "renderLoadingStates()" in html
    assert "DOMContentLoaded" in html


def test_dashboard_declares_state_renderer_with_kind_title_and_actions(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "function _renderState(container," in html
    assert "kind = \"empty\"" in html
    assert "title = \"\"" in html
    assert "actions = []" in html


def test_dashboard_declares_loading_empty_and_error_illustrations(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "function _stateIllustration(kind = \"empty\")" in html
    assert "if (kind === \"error\")" in html
    assert "if (kind === \"loading\")" in html


def test_dashboard_state_panel_keeps_accessible_action_markup(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "role=\"status\"" in html
    assert "aria-live=\"polite\"" in html
    assert "btn btn-secondary btn-xs" in html


def test_dashboard_speed_to_lead_empty_state_contract_copy_present(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "No agents running" in html
    assert "Create Agent" in html
    assert "Eingeschränkt verfügbar" in html


def test_dashboard_state_renderer_declares_html_escape_helper(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "function _escapeHtml(value = \"\")" in html
    assert ".replaceAll(\"<\", \"&lt;\")" in html
    assert ".replaceAll(\">\", \"&gt;\")" in html


def test_dashboard_state_renderer_declares_internal_href_guard(tmp_path, monkeypatch):
    html = _dashboard_html(tmp_path, monkeypatch)
    assert "function _safeActionHref(value = \"#\")" in html
    assert "if (!href.startsWith(\"/\")) return \"#\";" in html
    assert "if (href.startsWith(\"//\")) return \"#\";" in html
