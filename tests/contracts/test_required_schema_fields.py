from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_summary_contract_has_required_nested_contract_fields(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/summary")
    assert response.status_code == 200

    body = response.get_json()
    contract = body["details"]["contract"]
    assert "version" in contract
    assert isinstance(contract["version"], str)
    assert "read_only" in contract
    assert isinstance(contract["read_only"], bool)


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_health_contract_has_required_nested_contract_fields(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/health")
    assert response.status_code in {200, 503}

    body = response.get_json()
    contract = body["details"]["contract"]
    assert "version" in contract
    assert isinstance(contract["version"], str)
    assert "read_only" in contract
    assert isinstance(contract["read_only"], bool)
