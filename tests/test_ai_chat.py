from fastapi.testclient import TestClient

from kukanilea_app import app

client = TestClient(app)


def test_ai_chat_shortcut_suggestion():
    """Verify that the AI suggests a shortcut form instead of direct mutation."""
    headers = {"X-Tenant-ID": "test-tenant", "X-User-ID": "test-user", "X-Role": "ADMIN"}
    response = client.post(
        "/ai-chat/message",
        data={"message": "Erstelle aufmaß für Müller"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "KI-Vorschlag:" in response.text
    # Verify the presence of the confirm button/shortcut link
    # Using double quotes as in views.py
    assert 'hx-get="/crm/details/1"' in response.text
    assert "Formular prüfen & speichern" in response.text


def test_ai_chat_unhandled_message():
    """Verify handling of unknown messages."""
    headers = {"X-Tenant-ID": "test-tenant", "X-User-ID": "test-user", "X-Role": "ADMIN"}
    response = client.post(
        "/ai-chat/message", data={"message": "Hallo wie gehts"}, headers=headers
    )
    assert response.status_code == 200
    assert "konnte aber keinen eindeutigen Workflow zuordnen" in response.text
