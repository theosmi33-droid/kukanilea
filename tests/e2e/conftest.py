import pytest
import threading
import time
import os
from waitress import serve
from app import create_app

@pytest.fixture(scope="session", autouse=True)
def test_server():
    """Startet die KUKANILEA App im Hintergrund-Thread für Playwright Tests."""
    os.environ["KUKANILEA_AUTH_DB"] = "instance/test_auth.sqlite3"
    os.environ["KUKANILEA_CORE_DB"] = "instance/test_core.sqlite3"
    
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    # Gold-Edition Performance Bypass: Wir deaktivieren Lizenz- und Auth-Zwang für das Audit
    @app.before_request
    def test_bypass():
        from flask import session as flask_session, g
        flask_session["user"] = "testuser"
        flask_session["role"] = "DEV"
        flask_session["tenant_id"] = "KUKANILEA"
        flask_session["rbac_roles"] = ["DEV"]
        flask_session["rbac_perms"] = ["*"]
        
        g.user = "testuser"
        g.role = "DEV"
        g.tenant_id = "KUKANILEA"
        g.roles = ["DEV"]
        g.permissions = {"*"}
        
        # Mock license status
        from app.core.license_manager import license_manager
        license_manager._license_data = {"plan": "GOLD", "valid": True} 

    server_thread = threading.Thread(
        target=serve, 
        args=(app,), 
        kwargs={"host": "127.0.0.1", "port": 8080, "threads": 4}
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Warte bis der Server gebootet ist
    time.sleep(3)
    yield
    # Der Thread wird mit der Test-Session beendet
