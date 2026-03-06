from __future__ import annotations

from kukanilea.orchestrator import EventBus, ManagerAgent


def test_router_maps_intent_to_tools_deterministically() -> None:
    agent = ManagerAgent(external_calls_enabled=True)

    result = agent.route("Bitte zeige dashboard status", {"tenant": "KUKANILEA", "user": "admin"})

    assert result.ok is True
    assert result.status == "routed"
    assert result.decision.tool == "dashboard"
    assert result.decision.action == "summary"


def test_confirm_gate_blocks_critical_actions_without_confirm() -> None:
    bus = EventBus()
    agent = ManagerAgent(event_bus=bus)

    result = agent.route("Bitte erstelle eine Aufgabe", {"tenant": "KUKANILEA", "user": "admin"})

    assert result.ok is False
    assert result.status == "confirm_required"
    assert result.confirm_required is True
    assert bus.events[-1]["event_type"] == "manager_agent.confirm_blocked"


def test_confirm_gate_accepts_explicit_confirm_token() -> None:
    bus = EventBus()
    audit_payloads: list[dict] = []
    agent = ManagerAgent(
        event_bus=bus,
        audit_logger=lambda payload: audit_payloads.append(payload),
    )

    result = agent.route(
        "Bitte erstelle eine Aufgabe",
        {"tenant": "KUKANILEA", "user": "admin", "confirm": "YES"},
    )

    assert result.ok is True
    assert result.status == "routed"
    assert bus.events[-1]["event_type"] == "manager_agent.routed"
    assert audit_payloads[-1]["status"] == "routed"


def test_offline_first_blocks_external_action_without_feature_flag() -> None:
    bus = EventBus()
    agent = ManagerAgent(event_bus=bus, external_calls_enabled=False)

    result = agent.route("Sende bitte eine Messenger Nachricht", {"tenant": "KUKANILEA", "user": "admin", "confirm": "YES"})

    assert result.ok is False
    assert result.status == "offline_blocked"
    assert result.reason == "external_calls_disabled"
    assert bus.events[-1]["event_type"] == "manager_agent.offline_blocked"
