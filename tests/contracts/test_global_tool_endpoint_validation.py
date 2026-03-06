from __future__ import annotations


def test_global_summary_for_contract_tool_has_contract_shape(auth_client):
    response = auth_client.get('/api/calendar/summary')
    assert response.status_code == 200
    body = response.get_json()
    assert body['tool'] == 'calendar'


def test_global_health_rejects_invalid_tool_slug(auth_client):
    response = auth_client.get('/api/../health')
    assert response.status_code in {404, 308}


def test_global_summary_rejects_unknown_tool(auth_client):
    response = auth_client.get('/api/unknownzzz/summary')
    assert response.status_code == 404
    body = response.get_json()
    assert body['error'] == 'unknown_tool'
