"""
Unit-Tests für die PicoClaw Integration.
Verifiziert die strukturierte Datenextraktion und den ControllerAgent Flow.
"""

import pytest
import os
import json
from unittest.mock import MagicMock, patch
from app.ai.picoclaw_parser import picoclaw
from app.agents.orchestrator_v2 import ControllerAgent, wrap_tool_output

@pytest.fixture
def mock_image(tmp_path):
    img_path = tmp_path / "test_label.jpg"
    img_path.write_text("dummy image content")
    return str(img_path)

def test_picoclaw_regex_extraction():
    """Testet die heuristische Extraktion von Key-Value Paaren."""
    raw_text = "Modell: VSC-123
S/N: 987654321
Hersteller: Vaillant
Baujahr: 2022"
    extracted = picoclaw._parse_structured_data(raw_text)
    
    assert extracted["modell"] == "VSC-123"
    assert extracted["seriennummer"] == "987654321"
    assert extracted["hersteller"] == "Vaillant"
    assert extracted["baujahr"] == "2022"

@pytest.mark.asyncio
async def test_controller_agent_vision_flow(mock_image):
    """Verifiziert den Vision-Flow im ControllerAgent (PicoClaw -> Moondream)."""
    agent = ControllerAgent()
    agent.set_session_salt("test_salt")
    
    # Mock PicoClaw
    with patch("app.ai.picoclaw_parser.picoclaw.extract_data") as mock_extract:
        mock_extract.return_value = {"modell": "MOCK-1", "seriennummer": "123"}
        
        # Simuliere Vision Task
        res = await agent.process("Analysiere dieses Bild: Vision Task", "tenant_1", "user_1")
        
        assert "PicoClaw Extraktion" in res
        assert "MOCK-1" in res
        assert "<salt_test_salt>" in res

@pytest.mark.asyncio
async def test_controller_agent_vision_fallback(mock_image):
    """Testet den Fallback auf Moondream wenn PicoClaw nichts findet."""
    agent = ControllerAgent()
    agent.set_session_salt("test_salt")
    
    with patch("app.ai.picoclaw_parser.picoclaw.extract_data", return_value={}), 
         patch("app.ai.vision_parser.vision_parser.analyze_image", return_value="Szenenbeschreibung") as mock_moondream:
        
        res = await agent.process("Analysiere dieses Bild: Vision Task", "tenant_1", "user_1")
        
        assert "Moondream Analyse (Fallback)" in res
        assert "Szenenbeschreibung" in res
        assert mock_moondream.called
