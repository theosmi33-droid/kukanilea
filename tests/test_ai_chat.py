"""
tests/test_ai_chat.py
E2E & Integration tests for the KUKANILEA AI Chat (FastAPI).
Verifies Read-Only, Intent Parsing, and Local LLM fallback.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from kukanilea_app import app


@pytest.fixture
def client():
    return TestClient(app)

def test_chat_interface_status(client):
    """Verifies the chat interface endpoint is accessible."""
    resp = client.get("/ai-chat/")
    assert resp.status_code == 200

def test_chat_message_shortcut(client):
    """Verifies that the 'Aufgabe:' shortcut triggers the intent parser."""
    # This should return the shortcuts.html content
    resp = client.post("/ai-chat/message", data={"message": "Aufgabe: Test Task"})
    assert resp.status_code == 200
    assert b"Test Task" in resp.content

@patch("app.ai_chat.views.ask_local_ai")
def test_chat_message_ai_fallback(mock_ask_ai, client):
    """Verifies that unknown input falls back to the local AI engine."""
    mock_ask_ai.return_value = "Das ist ein lokaler Test."
    
    resp = client.post("/ai-chat/message", data={"message": "Wie ist das Wetter?"})
    
    assert resp.status_code == 200
    assert b"Das ist ein lokaler Test." in resp.content
    mock_ask_ai.assert_called_once_with("Wie ist das Wetter?", tenant_id="KUKANILEA")

def test_chat_message_empty(client):
    """Verifies empty messages are ignored."""
    resp = client.post("/ai-chat/message", data={"message": ""})
    assert resp.status_code == 200
    assert resp.text == ""
