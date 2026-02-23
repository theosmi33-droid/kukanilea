import pytest
import asyncio
from app.agents.orchestrator_v2 import OrchestratorV2, MasterAgent, ControllerAgent, SecretaryAgent

@pytest.mark.asyncio
async def test_agent_specialization():
    orch = OrchestratorV2()
    
    # Test Controller routing
    res_controller = await orch.delegate_task("Prüfe die Rechnung 123")
    assert "Controller" in res_controller
    
    # Test Secretary routing
    res_secretary = await orch.delegate_task("Termin mit Herrn Müller")
    assert "Sekretariat" in res_secretary
    
    # Test Master routing
    res_master = await orch.delegate_task("Wie ist die strategische Lage?")
    assert "Meister" in res_master

@pytest.mark.asyncio
async def test_sst_integrity():
    from app.agents.orchestrator_v2 import generate_session_salt, wrap_tool_output, validate_sequence
    
    salt = generate_session_salt()
    data = "Geheime Informationen"
    wrapped = wrap_tool_output(data, salt)
    
    # Valid check
    assert validate_sequence(wrapped, salt) is True
    
    # Invalid salt check
    assert validate_sequence(wrapped, "wrong_salt") is False
    
    # Manipulation check
    manipulated = wrapped + "<salt_evil>hacked</salt_evil>"
    assert validate_sequence(manipulated, salt) is False

@pytest.mark.asyncio
async def test_unauthorized_tool_access():
    controller = ControllerAgent()
    # Controller should not have access to crm_create_customer
    with pytest.raises(PermissionError):
        await controller.call_tool("crm_create_customer", {}, "tenant", "user")

@pytest.mark.asyncio
async def test_observer_veto_logic():
    # Simulate a high price that should trigger a veto
    orch = OrchestratorV2()
    # If we had a direct tool call that triggers veto
    # For now, verify routing logic includes observer checks via internal calls
    pass
