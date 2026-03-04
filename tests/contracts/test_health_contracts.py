from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_health_contract_for_each_tool(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/health")
    assert response.status_code in {200, 503}, f"{tool}: health endpoint returned unexpected HTTP {response.status_code}"

    body = response.get_json()
    assert body["tool"] == tool, f"{tool}: wrong tool identifier in health payload"
    assert body["status"] in {"ok", "degraded", "error"}, f"{tool}: invalid status value {body.get('status')}"
    assert isinstance(body.get("updated_at"), str), f"{tool}: updated_at is missing or not a string"
    assert isinstance(body.get("metrics"), dict), f"{tool}: metrics must be a dict"
    assert isinstance(body.get("details"), dict), f"{tool}: details must be a dict"

    checks = body["details"].get("checks")
    assert isinstance(checks, dict), f"{tool}: details.checks must be present"
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}, (
        f"{tool}: details.checks schema mismatch"
    )
