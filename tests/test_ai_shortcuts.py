"""
tests/test_ai_shortcuts.py
Evidence Test für EPIC 7: Conversation as Shortcut.
Verifiziert das Human-in-the-loop Gate.
"""
import pytest
from fastapi.testclient import TestClient
from kukanilea_app import app
from app.database import get_db_connection, init_db

client = TestClient(app)

def test_ai_task_shortcut_proposal():
    """
    Verifiziert, dass die KI einen Task-Vorschlag macht, 
    aber keine direkte Datenbank-Mutation durchführt.
    """
    init_db()
    tenant = "test_ai_user"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": "tester", "X-Role": "USER"}
    
    # 1. Nutzer sendet Nachricht
    msg = "Erstelle eine neue Aufgabe: Dachziegel bestellen"
    response = client.post("/ai-chat/message", data={"message": msg}, headers=headers)
    
    assert response.status_code == 200
    assert "KI-Vorschlag: Neue Aufgabe" in response.text
    assert "Dachziegel bestellen" in response.text
    # Der Vorschlag muss einen Link zum eigentlichen Formular enthalten
    assert 'hx-get="/tasks/"' in response.text
    
    # 2. Verifikation: Datenbank muss für diesen Tenant leer bleiben (kein Auto-Inject!)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM entities WHERE tenant_id = ? AND type = 'task'", (tenant,))
    count = cursor.fetchone()[0]
    assert count == 0, "Security Violation: AI mutated database without human confirmation!"
    conn.close()

def test_ai_unknown_fallback():
    """Verifiziert die AI Act konforme Antwort bei Unklarheit."""
    headers = {"X-Tenant-ID": "test", "X-User-ID": "tester", "X-Role": "USER"}
    response = client.post("/ai-chat/message", data={"message": "Erzähl mir einen Witz"}, headers=headers)
    assert response.status_code == 200
    assert "konnte aber keinen eindeutigen Workflow zuordnen" in response.text
