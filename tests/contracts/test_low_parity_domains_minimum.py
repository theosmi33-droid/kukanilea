from __future__ import annotations


def test_messenger_summary_exposes_runtime_and_confirm_contract(auth_client):
    response = auth_client.get("/api/messenger/summary")
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] in {"ok", "degraded"}
    assert body["metrics"]["confirm_gate"] == 1
    runtime = body["details"]["runtime"]
    assert runtime["routes"]["chat_api"] is True
    assert runtime["routes"]["summary_api"] is True
    assert runtime["intake_parser_ready"] is True
    assert body["details"]["confirm_gate"] is True


def test_email_summary_reports_postfach_runtime_and_confirm_gate(auth_client):
    response = auth_client.get("/api/email/summary")
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] in {"ok", "degraded"}
    assert body["metrics"]["confirm_gate"] == 1
    assert isinstance(body["metrics"]["unread_count"], int)
    assert isinstance(body["metrics"]["open_drafts"], int)
    assert isinstance(body["metrics"]["audit_events"], int)

    runtime = body["details"]["runtime"]
    assert runtime["routes"]["legacy_summary"] is True
    assert runtime["routes"]["legacy_health"] is True
    assert runtime["routes"]["postfach_summary"] is True
    assert runtime["routes"]["postfach_ingest"] is True
    assert runtime["routes"]["postfach_send"] is True
    assert runtime["confirm_gate"] is True


def test_visualizer_summary_reports_runtime_readiness_state(auth_client):
    response = auth_client.get("/api/visualizer/summary")
    assert response.status_code == 200
    body = response.get_json()

    assert body["status"] in {"ok", "degraded"}
    assert isinstance(body["metrics"]["render_backend_ready"], int)
    assert isinstance(body["metrics"]["markup_ready"], int)
    assert isinstance(body["metrics"]["sources_indexed"], int)

    runtime = body["details"]["runtime"]
    assert runtime["routes"]["sources"] is True
    assert runtime["routes"]["render"] is True
    assert runtime["routes"]["summary"] is True
    assert runtime["routes"]["markup_get"] is True
    assert runtime["routes"]["markup_post"] is True

    if body["metrics"]["render_backend_ready"] == 0:
        assert body["status"] == "degraded"
        assert body.get("degraded_reason") == "visualizer_logic_missing"


def test_visualizer_summary_degraded_when_backend_missing(monkeypatch):
    from app.contracts import tool_contracts

    original = tool_contracts._core_get

    def _fake_core_get(name: str, default=None):
        if name == "build_visualizer_payload":
            return None
        return original(name, default)

    monkeypatch.setattr(tool_contracts, "_core_get", _fake_core_get)
    payload = tool_contracts.build_tool_summary("visualizer", tenant="KUKANILEA")
    assert payload["status"] == "degraded"
    assert payload.get("degraded_reason") == "visualizer_logic_missing"


def test_visualizer_summary_reports_markup_not_ready(monkeypatch):
    import app.core.visualizer_markup as markup
    from app.contracts import tool_contracts

    monkeypatch.setattr(markup, "append_markup", None, raising=False)
    payload = tool_contracts.build_tool_summary("visualizer", tenant="KUKANILEA")
    assert payload["metrics"]["markup_ready"] == 0
    assert payload["details"]["runtime"]["markup_ready"] is False
