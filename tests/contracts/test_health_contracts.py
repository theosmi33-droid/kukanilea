from flask import Flask

from app.core.integration_contracts import TOOL_KEYS
from app.web import bp as web_bp


def _client():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(web_bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session["user"] = "tester"
        session["role"] = "DEV"
        session["tenant_id"] = "default"
    return client


def test_health_contracts_for_all_tools():
    client = _client()
    for tool in TOOL_KEYS:
        response = client.get(f"/api/{tool}/health")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["tool"] == tool
        assert payload["status"] in {"healthy", "degraded", "down"}
        assert payload["updated_at"]
        assert isinstance(payload["metrics"], dict)
        assert isinstance(payload["details"], dict)
