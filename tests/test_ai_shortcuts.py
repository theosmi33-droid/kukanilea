"""
tests/test_ai_shortcuts.py
Release Gate Q-SCAN: Verifiziert das Human-in-the-Loop AI Feature.
"""

import pytest
from app import create_app
from app.database import get_db_connection, init_db, DB_PATH
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    # Setup test DB
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    app = create_app()
    app.config["TESTING"] = True
    
    with app.app_context():
        init_db()
        
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_ai_shortcut_create_task_form(client):
    """
    Testet, ob 'Aufgabe: [Titel]' ein Formular zurückgibt,
    aber KEINE Daten in die DB schreibt.
    """
    
    # Inject session data to bypass auth redirects
    with client.session_transaction() as sess:
        sess['user'] = 'test_user'
        sess['tenant_id'] = 'test_tenant'
        sess['role'] = 'ADMIN'

    # Mock tenant context to avoid redirects
    with patch("app.tenant.context.load_tenant_context") as mock_load:
        mock_ctx = MagicMock()
        mock_ctx.tenant_id = "test_tenant"
        mock_load.return_value = mock_ctx
        
        # 1. Stand vor dem Request prüfen
        conn = get_db_connection()
        count_before = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        conn.close()
        
        # 2. KI-Shortcut triggern
        response = client.post(
            "/ai-chat/message",
            data={"message": "Aufgabe: Gerüst abbauen"},
            headers={"Accept": "text/html"},
            follow_redirects=True
        )
        
        # 3. Assertions
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        
        # Sicherstellen, dass ein Formular mit dem Titel zurückgegeben wird
        assert "<form" in html
        assert 'value="Gerüst abbauen"' in html
        assert 'hx-post="/tasks/new"' in html
        
        # 4. Verifizieren, dass KEIN DB-Eintrag erzeugt wurde (Read-Only)
        conn = get_db_connection()
        count_after = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        conn.close()
        
        assert count_before == count_after, "KI hat unerlaubt in die DB geschrieben!"
