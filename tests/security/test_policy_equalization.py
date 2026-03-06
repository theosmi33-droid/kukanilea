import pytest
from kukanilea.orchestrator.orchestrator import Orchestrator
from kukanilea.agents import AgentContext
from app.tools.action_registry import action_registry
from app.core.tool_loader import load_all_tools

class MockCore:
    def audit_log(self, **kwargs): pass
    def task_create(self, **kwargs): pass

@pytest.fixture
def orchestrator():
    load_all_tools()
    return Orchestrator(MockCore())

def test_policy_engine_dynamic_lookup(orchestrator):
    # Test READONLY role for a low risk action
    # CORE.GENERIC.SEARCH is LOW risk
    assert orchestrator.policy.policy_check("READONLY", "KUKANILEA", "CORE.GENERIC.SEARCH", "global") is True

def test_policy_engine_admin_required_for_high_risk(orchestrator):
    # Test that OPERATOR cannot do a HIGH risk action
    # CORE.GENERIC.EXECUTE is HIGH risk (because of the suffix)
    assert orchestrator.policy.policy_check("OPERATOR", "KUKANILEA", "CORE.GENERIC.EXECUTE", "global") is False
    assert orchestrator.policy.policy_check("ADMIN", "KUKANILEA", "CORE.GENERIC.EXECUTE", "global") is True

def test_orchestrator_allowed_tools_sync(orchestrator):
    # Check if a tool from the registry is in allowed_tools
    assert "CORE.GENERIC.EXECUTE" in orchestrator.allowed_tools
    assert "CORE.GENERIC" in orchestrator.allowed_tools # short name
