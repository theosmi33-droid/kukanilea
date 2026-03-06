from __future__ import annotations

import pytest
from app.core.agent_router import plan_actions
from app.tools.action_registry import action_registry
from app.tools.base_tool import BaseTool

class DummyMailTool(BaseTool):
    name = "dummy_mail"
    domain = "EMAILPOSTFACH"
    entity = "MAIL"

def test_router_resolves_hierarchical_action_from_keywords():
    # Register the tool
    tool = DummyMailTool()
    action_registry.register_tool(tool)
    
    # We expect EMAILPOSTFACH.MAIL.SEND to be registered (suffix 'send')
    action_name = "EMAILPOSTFACH.MAIL.SEND"
    assert action_name in action_registry._actions_by_name
    
    # Test message that should match domain (EMAILPOSTFACH/mail) and verb (send)
    message = "Sende eine Mail an chef@kukanilea.de"
    context = {"tenant": "alpha", "user_id": "u-1"}
    
    plan = plan_actions(message, context)
    
    # Verify the router picked the specific action instead of generic core.write_action
    assert plan["steps"][0]["tool"] == action_name
    assert plan["steps"][0]["action_type"] == "write"

def test_router_fallback_on_ambiguous_intent():
    message = "irgendwas machen"
    plan = plan_actions(message, {})
    
    # Should either be clarify or a generic fallback
    assert plan["steps"][0]["tool"] in {"clarify.intent", "core.write_action", "core.read_action"}
