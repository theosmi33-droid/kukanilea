import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app import create_app
from app.agents import orchestrator

def test_chatbot():
    print("--- KUKANILEA Chatbot Audit ---")
    app = create_app()
    with app.app_context():
        print("[1/3] Testing empty message handling...")
        res = orchestrator.answer("")
        assert res["text"] == "Bitte gib eine Nachricht ein.", f"Failed empty msg: {res}"
        
        print("[2/3] Testing action parsing & dispatch...")
        with patch('app.agents.llm_ollama.generate') as mock_llm:
            mock_llm.return_value = '{"action": "create_task", "args": {"title": "Test Task", "tenant": "default", "severity": "info", "task_type": "general"}}'
            res = orchestrator.answer("Erstelle einen Task Test Task")
            print(f"Full response: {res}")
            print(f"Action parsed: {res.get('action')}")
            assert res.get("action") is not None, "Failed to parse action from LLM output"
            assert res["action"]["name"] == "create_task", "Parsed wrong action name"
        
        print("[3/3] Testing plain text response...")
        with patch('app.agents.llm_ollama.generate') as mock_llm:
            mock_llm.return_value = "Hier sind die Fakten."
            res = orchestrator.answer("Was gibt es neues?")
            print(f"Text response: {res.get('text')}")
            assert "Hier sind die Fakten" in res["text"] or "Fakten" in res["text"], "Text fallback failed"

    print("\n[PASSED] Chatbot Audit complete. All tests passed.")

if __name__ == "__main__":
    test_chatbot()
