from __future__ import annotations


def test_dashboard_summary_declares_aggregation_contract(auth_client):
    response = auth_client.get("/api/dashboard/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "dashboard"
    assert body["details"]["matrix_endpoint"] == "/api/dashboard/tool-matrix"
    assert body["details"]["aggregate_mode"] == "summary_only"


def test_chatbot_summary_declares_payload_aliases(auth_client):
    response = auth_client.get("/api/chatbot/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "chatbot"

    contract = body["details"]["payload_contract"]
    assert contract["request_fields"] == ["message", "msg", "q"]
    assert contract["response_fields"] == ["ok", "response"]
