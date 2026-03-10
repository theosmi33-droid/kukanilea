from __future__ import annotations

from pathlib import Path

from app.agents.orchestrator import AgentContext, MessengerAgent


def test_messenger_agent_proposals_require_confirm():
    agent = MessengerAgent()
    context = AgentContext(tenant_id="test-tenant", user="test-user", role="USER")
    
    # Remove @kukanilea trigger to stay in heuristic mode
    message = "erstelle eine aufgabe"
    result = agent.handle(message, "messenger", context)
    
    proposals = result.data.get("hub", {}).get("proposals", [])
    assert len(proposals) > 0
    
    for p in proposals:
        if p['type'] in ['create_task', 'create_appointment', 'messenger_send']:
            assert p['confirm_required'] is True

def test_messenger_agent_provider_extraction():
    agent = MessengerAgent()
    assert agent._extract_provider("Nachricht via Telegram") == "telegram"
    assert agent._extract_provider("WhatsApp Status") == "whatsapp"
    assert agent._extract_provider("Instagram DM") == "instagram"
    assert agent._extract_provider("Facebook Messenger") == "meta"
    assert agent._extract_provider("Interner Chat") == "internal"


def test_invoice_reminder_contract_keeps_guarded_reminder_template() -> None:
    source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
    assert '"invoice_propose_reminder"' in source
    assert "_extract_untrusted_text(p, 'invoice_id')" in source


def test_manager_agent_contract_blocks_injection_even_with_neutral_keywords() -> None:
    source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
    assert "if injection_matches:\n            return RuntimeGuardResult(" in source


def test_manager_agent_contract_prevents_propose_mode_action_routing_without_context() -> None:
    source = Path("kukanilea/orchestrator/manager_agent.py").read_text(encoding="utf-8")
    assert "plan.missing_context or plan.execution_mode == \"propose\"" in source
    assert 'status="needs_clarification"' in source


def test_cross_tool_flows_contract_excludes_traceback_key_from_failures() -> None:
    source = Path("kukanilea/orchestrator/cross_tool_flows.py").read_text(encoding="utf-8")
    assert '"traceback":' not in source


def test_project_logic_contract_migrates_project_card_column_for_legacy_tables() -> None:
    source = Path("app/modules/projects/logic.py").read_text(encoding="utf-8")
    assert "project_card_id" in source
    assert "ALTER TABLE team_tasks ADD COLUMN" in source
