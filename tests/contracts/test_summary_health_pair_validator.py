from __future__ import annotations

from app.contracts import tool_contracts


def test_summary_health_pair_validator_accepts_valid_payloads() -> None:
    summary = tool_contracts.build_tool_summary("upload", tenant="KUKANILEA")
    health = tool_contracts.build_tool_health("upload", tenant="KUKANILEA")

    errors = tool_contracts.validate_summary_health_pair(summary, health)

    assert errors == []


def test_summary_health_pair_validator_detects_contract_mismatches() -> None:
    summary = tool_contracts.build_tool_summary("upload", tenant="KUKANILEA")
    health = tool_contracts.build_tool_health("upload", tenant="KUKANILEA")
    health["details"]["contract"]["version"] = "2099-01-01"
    health["details"]["contract"]["read_only"] = not bool(summary["details"]["contract"]["read_only"])
    health["details"]["contract"]["kind"] = "summary"
    health["details"]["tenant"] = "OTHER"

    errors = tool_contracts.validate_summary_health_pair(summary, health)

    assert "health:mismatch:details.contract.kind" in errors
    assert "mismatch:contract.version" in errors
    assert "mismatch:contract.read_only" in errors
    assert "mismatch:tenant" in errors


def test_validate_tool_contract_payload_checks_expected_tool() -> None:
    payload = tool_contracts.build_tool_summary("tasks", tenant="KUKANILEA")

    errors = tool_contracts.validate_tool_contract_payload(payload, expected_tool="upload", expected_kind="summary")

    assert "mismatch:tool" in errors
