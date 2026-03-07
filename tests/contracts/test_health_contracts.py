from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS


REQUIRED_FIELDS = {"tool", "status", "updated_at", "metrics", "details"}


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_health_contract_for_each_tool(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/health")
    assert response.status_code in {200, 503}, f"{tool}: health endpoint returned unexpected HTTP {response.status_code}"

    body = response.get_json()
    assert REQUIRED_FIELDS.issubset(body.keys()), f"{tool}: missing required top-level fields"
    assert body["tool"] == tool, f"{tool}: wrong tool identifier in health payload"
    assert body["status"] in {"ok", "degraded", "error"}, f"{tool}: invalid status value {body.get('status')}"
    assert isinstance(body.get("updated_at"), str), f"{tool}: updated_at is missing or not a string"
    assert isinstance(body.get("metrics"), dict), f"{tool}: metrics must be a dict"
    assert isinstance(body.get("details"), dict), f"{tool}: details must be a dict"
    assert isinstance(body["details"].get("contract"), dict), f"{tool}: details.contract must be a dict"
    assert isinstance(body["details"]["contract"].get("version"), str), f"{tool}: details.contract.version must be present"
    assert isinstance(body["details"]["contract"].get("read_only"), bool), f"{tool}: details.contract.read_only must be bool"
    assert body["details"]["contract"].get("kind") == "health", f"{tool}: details.contract.kind must be health"

    checks = body["details"].get("checks")
    assert isinstance(checks, dict), f"{tool}: details.checks must be present"
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}, (
        f"{tool}: details.checks schema mismatch"
    )
