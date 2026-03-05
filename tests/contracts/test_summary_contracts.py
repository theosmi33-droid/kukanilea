from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS


REQUIRED_FIELDS = {"tool", "status", "ts", "summary", "warnings", "links"}


@pytest.mark.parametrize("tool", CONTRACT_TOOLS)
def test_summary_contract_for_each_tool(auth_client, tool):
    response = auth_client.get(f"/api/{tool}/summary")
    assert response.status_code == 200, f"{tool}: expected HTTP 200 for summary, got {response.status_code}"

    body = response.get_json()
    assert REQUIRED_FIELDS.issubset(body.keys()), f"{tool}: missing required top-level fields"
    assert body["tool"] == tool, f"{tool}: wrong tool identifier in summary payload"
    assert body["status"] in {"ok", "degraded", "error"}, f"{tool}: invalid status value {body.get('status')}"
    assert isinstance(body.get("ts"), str), f"{tool}: ts is missing or not a string"
    assert isinstance(body.get("summary"), dict), f"{tool}: summary must be a dict"
    assert isinstance(body.get("warnings"), list), f"{tool}: warnings must be a list"
    assert isinstance(body.get("links"), dict), f"{tool}: links must be a dict"
    assert body["links"]["summary"] == f"/api/{tool}/summary"
    assert body["links"]["health"] == f"/api/{tool}/health"
