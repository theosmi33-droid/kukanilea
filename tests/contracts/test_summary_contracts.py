from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_summary_contract_for_each_tool(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/summary")
    assert response.status_code == 200, f"{tool}: expected HTTP 200 for summary, got {response.status_code}"

    body = response.get_json()
    assert body["tool"] == tool, f"{tool}: wrong tool identifier in summary payload"
    assert body["status"] in {"ok", "degraded", "error"}, f"{tool}: invalid status value {body.get('status')}"
    assert isinstance(body.get("updated_at"), str), f"{tool}: updated_at is missing or not a string"
    assert isinstance(body.get("metrics"), dict), f"{tool}: metrics must be a dict"
    assert isinstance(body.get("details"), dict), f"{tool}: details must be a dict"
    assert isinstance(body["details"].get("contract"), dict), f"{tool}: details.contract must be a dict"
    assert body.get("tenant") == "KUKANILEA", f"{tool}: summary tenant must match active session"
    assert body["details"].get("tenant") == "KUKANILEA", f"{tool}: details.tenant must match active session"
    assert isinstance(body["details"]["contract"].get("version"), str), f"{tool}: details.contract.version must be present"
    assert isinstance(body["details"]["contract"].get("read_only"), bool), f"{tool}: details.contract.read_only must be bool"
    if body["status"] == "degraded":
        assert isinstance(body.get("degraded_reason"), str) and body.get("degraded_reason"), (
            f"{tool}: degraded status must include non-empty degraded_reason"
        )
