from __future__ import annotations

import pytest
from app.agents.mail import MailAgent
from app.agents.base import AgentContext

def test_mail_agent_send_requires_confirm():
    agent = MailAgent()
    context = AgentContext(tenant_id="test", user="test", role="OPERATOR")
    
    # Message triggering send action
    result = agent.handle("schicke die Mail ab", "mail", context)
    
    assert len(result.actions) == 1
    assert result.actions[0]["type"] == "mail_send"
    assert result.actions[0]["confirm_required"] is True

def test_mail_agent_default_response():
    agent = MailAgent()
    context = AgentContext(tenant_id="test", user="test", role="OPERATOR")
    
    result = agent.handle("hallo", "mail", context)
    assert "Mail-Entwürfe" in result.text
    assert len(result.actions) == 0
