from __future__ import annotations

import app.modules.messenger as messenger_module
from app.contracts import tool_contracts


def test_messenger_summary_ok_runtime_and_audit_sink(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_contracts,
        "_route_available",
        lambda route, method: route in {
            "/api/chat",
            "/api/messenger/summary",
            "/api/messenger/health",
            "/messenger",
        },
    )
    monkeypatch.setattr(
        messenger_module,
        "parse_chat_intake",
        lambda message, actions=None: {
            "suggested_next_actions": [{"type": "create_task", "confirm_required": True}]
        },
    )
    monkeypatch.setattr(
        tool_contracts,
        "_core_get",
        lambda name, default=None: (lambda **kwargs: None) if name == "audit_log" else default,
    )

    metrics, details, reason = tool_contracts._collect_messenger_summary("KUKANILEA")

    assert reason == ""
    assert details["runtime"]["routes"]["chat_api"] is True
    assert details["runtime"]["routes"]["summary_api"] is True
    assert details["runtime"]["routes"]["health_api"] is True
    assert details["runtime"]["routes"]["messenger_page"] is True
    assert details["runtime"]["intake_parser_ready"] is True
    assert details["runtime"]["audit_sink_ready"] is True
    assert metrics["confirm_gate"] == 1
    assert metrics["audit_sink_ready"] == 1


def test_messenger_summary_degrades_when_route_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_contracts,
        "_route_available",
        lambda route, method: route in {"/api/chat", "/api/messenger/summary"},
    )
    monkeypatch.setattr(
        messenger_module,
        "parse_chat_intake",
        lambda message, actions=None: {
            "suggested_next_actions": [{"type": "create_task", "confirm_required": True}]
        },
    )

    metrics, details, reason = tool_contracts._collect_messenger_summary("KUKANILEA")

    assert reason == "messenger_routes_missing"
    assert metrics["confirm_gate"] == 1
    assert details["runtime"]["routes"]["health_api"] is False
    assert details["runtime"]["routes"]["messenger_page"] is False


def test_messenger_summary_degrades_on_parser_error_without_crash(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_contracts,
        "_route_available",
        lambda _route, _method: True,
    )

    def _boom(_message, actions=None):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(messenger_module, "parse_chat_intake", _boom)

    metrics, details, reason = tool_contracts._collect_messenger_summary("KUKANILEA")

    assert reason == "messenger_confirm_contract_unavailable"
    assert metrics["confirm_gate"] == 0
    assert details["runtime"]["intake_parser_ready"] is False
    assert "parser_error" in details["runtime"]
    assert "parser exploded" in details["runtime"]["parser_error"]
