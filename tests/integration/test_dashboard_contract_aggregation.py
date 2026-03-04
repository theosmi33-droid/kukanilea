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


def test_dashboard_contract_aggregation_uses_standard_contracts():
    client = _client()
    aggregation = client.get("/api/dashboard/contracts")
    assert aggregation.status_code == 200
    body = aggregation.get_json()

    assert body["status"] in {"ok", "degraded"}
    assert body["metrics"]["tool_count"] == len(TOOL_KEYS)

    summaries = body["details"]["summaries"]
    health = body["details"]["health"]
    assert set(summaries.keys()) == set(TOOL_KEYS)
    assert set(health.keys()) == set(TOOL_KEYS)

    for tool in TOOL_KEYS:
        summary_response = client.get(f"/api/{tool}/summary")
        health_response = client.get(f"/api/{tool}/health")
        assert summaries[tool]["status"] == summary_response.get_json()["status"]
        assert health[tool]["status"] == health_response.get_json()["status"]
