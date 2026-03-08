from __future__ import annotations

import pytest

from app.contracts import tool_contracts


EXPECTED_TOOLS = tuple(tool_contracts.CONTRACT_TOOLS)
EXPECTED_TOP_LEVEL_FIELDS = {"tool", "status", "updated_at", "metrics", "details"}
EXPECTED_STATUSES = tool_contracts.CONTRACT_STATUSES
EXPECTED_KINDS = {"summary", "health"}


@pytest.mark.parametrize("tool", EXPECTED_TOOLS)
@pytest.mark.parametrize("kind", ("summary", "health"))
def test_schema_lock_for_summary_and_health_contracts(tool: str, kind: str) -> None:
    payload = (
        tool_contracts.build_tool_summary(tool, tenant="KUKANILEA")
        if kind == "summary"
        else tool_contracts.build_tool_health(tool, tenant="KUKANILEA")
    )

    assert set(payload.keys()).issuperset(EXPECTED_TOP_LEVEL_FIELDS)
    assert payload["tool"] == tool
    assert payload["status"] in EXPECTED_STATUSES
    assert isinstance(payload["updated_at"], str) and payload["updated_at"]
    assert isinstance(payload["metrics"], dict)
    assert isinstance(payload["details"], dict)

    contract = payload["details"].get("contract")
    assert isinstance(contract, dict)
    assert set(contract.keys()) == {"version", "read_only", "kind"}
    assert isinstance(contract["version"], str) and contract["version"]
    assert isinstance(contract["read_only"], bool)
    assert contract["kind"] in EXPECTED_KINDS
    assert contract["kind"] == kind


@pytest.mark.parametrize("tool", EXPECTED_TOOLS)
def test_summary_health_lockstep_fields_match(tool: str) -> None:
    summary = tool_contracts.build_tool_summary(tool, tenant="KUKANILEA")
    health = tool_contracts.build_tool_health(tool, tenant="KUKANILEA")

    assert summary["status"] in EXPECTED_STATUSES
    assert health["status"] in EXPECTED_STATUSES
    assert summary["details"]["contract"]["version"] == health["details"]["contract"]["version"]
    assert summary["details"]["contract"]["read_only"] == health["details"]["contract"]["read_only"]
    assert summary["details"]["contract"]["kind"] == "summary"
    assert health["details"]["contract"]["kind"] == "health"
