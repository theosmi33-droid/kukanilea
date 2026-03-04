from __future__ import annotations

import pytest
from app.agents.orchestrator import MessengerAgent, AgentContext

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
