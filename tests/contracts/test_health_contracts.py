from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS


REQUIRED_FIELDS = {"tool", "status", "ts", "summary", "warnings", "links"}


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_health_contract_for_each_tool(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/health")
    assert response.status_code in {200, 503}, f"{tool}: health endpoint returned unexpected HTTP {response.status_code}"

    body = response.get_json()
    assert REQUIRED_FIELDS.issubset(body.keys()), f"{tool}: missing required top-level fields"
    assert body["tool"] == tool, f"{tool}: wrong tool identifier in health payload"
    assert body["status"] in {"ok", "degraded", "error"}, f"{tool}: invalid status value {body.get('status')}"
    assert isinstance(body.get("ts"), str), f"{tool}: ts is missing or not a string"
    assert isinstance(body.get("summary"), dict), f"{tool}: summary must be a dict"
    assert isinstance(body.get("warnings"), list), f"{tool}: warnings must be a list"
    assert isinstance(body.get("links"), dict), f"{tool}: links must be a dict"

    checks = body["summary"].get("details", {}).get("checks")
    assert isinstance(checks, dict), f"{tool}: details.checks must be present"
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}, (
        f"{tool}: details.checks schema mismatch"
    )
