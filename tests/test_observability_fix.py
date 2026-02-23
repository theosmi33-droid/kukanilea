import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.autonomy.healer import init_healer, set_degraded_mode
from app.autonomy.maintenance import check_integrity
from app.observability import setup_observability


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    setup_observability(app)
    init_healer(app)
    
    @app.route("/test", methods=["GET", "POST"])
    def test_route():
        return "ok"
        
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_degraded_mode_api(client):
    set_degraded_mode(True)
    try:
        # API request (Accept: application/json)
        response = client.post("/test", headers={"Accept": "application/json"})
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["error"] == "degraded_mode"
        
        # GET should still work
        response = client.get("/test")
        assert response.status_code == 200
    finally:
        set_degraded_mode(False)

def test_degraded_mode_ui(client):
    set_degraded_mode(True)
    try:
        # UI request (Accept: text/html)
        response = client.post("/test", headers={"Accept": "text/html"})
        assert response.status_code == 503
        assert b"Degraded Mode" in response.data
        assert b"html" in response.data
    finally:
        set_degraded_mode(False)

@patch("app.autonomy.maintenance.get_db_connection")
def test_integrity_check_multi_row(mock_get_conn):
    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn
    
    # Simulate multiple error rows
    mock_conn.execute.return_value.fetchall.return_value = [("Main index corruption",), ("Unused pages found",)]
    
    assert check_integrity() is False
    
    # Simulate success
    mock_conn.execute.return_value.fetchall.return_value = [("ok",)]
    assert check_integrity() is True
