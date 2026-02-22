import pytest
from fastapi.testclient import TestClient
from kukanilea_app import app

client = TestClient(app)

def test_ai_chat_shortcut_suggestion():
    """Verify that the AI suggests a shortcut form instead of direct mutation."""
    response = client.post("/ai-chat/message", data={"message": "Erstelle aufmaß für Müller"})
    assert response.status_code == 200
    assert "KI-Vorschlag:" in response.text
    # Verify the presence of the confirm button/shortcut link
    # Using double quotes as in views.py
    assert 'hx-get="/crm/details/1"' in response.text
    assert "Formular prüfen & speichern" in response.text

def test_ai_chat_unhandled_message():
    """Verify handling of unknown messages."""
    response = client.post("/ai-chat/message", data={"message": "Hallo wie gehts"})
    assert response.status_code == 200
    assert "Aktuell kann ich nur Aufmaße vorbereiten" in response.text
