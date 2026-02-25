import json
from pathlib import Path

import pytest
from flask import Flask

from app.observability import init_observability


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__)
    log_dir = tmp_path / "test_logs"
    app.config["LOG_DIR"] = str(log_dir)
    app.config["TENANT_DEFAULT"] = "TEST_TENANT"
    init_observability(app)
    
    @app.route("/test")
    def test_route():
        return "ok"

    @app.route("/error")
    def error_route():
        raise ValueError("test error")
        
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_request_id_header(client):
    response = client.get("/test")
    assert response.status_code == 200
    assert "X-Request-Id" in response.headers

def test_json_logging(client, app):
    log_file = Path(app.config["LOG_DIR"]) / "app.jsonl"
    
    client.get("/test")
    
    assert log_file.exists()
    with open(log_file, "r") as f:
        line = f.readline()
        log_data = json.loads(line)
        assert log_data["route"] == "/test"
        assert log_data["status_code"] == 200
        assert "request_id" in log_data
        import hashlib
        expected_hash = hashlib.sha256(b"TEST_TENANT").hexdigest()[:12]
        assert log_data["tenant_hash"] == expected_hash
        assert "duration_ms" in log_data

def test_error_logging(client, app):
    log_file = Path(app.config["LOG_DIR"]) / "app.jsonl"
    
    response = client.get("/error")
    assert response.status_code == 500
    
    assert log_file.exists()
    with open(log_file, "r") as f:
        lines = f.readlines()
        # The log_request in after_request should have the error_class
        last_log = json.loads(lines[-1])
        assert last_log["error_class"] == "ValueError"
        assert last_log["route"] == "/error"
        assert last_log["status_code"] == 500
