from __future__ import annotations

from app.contracts import tool_contracts


def test_each_contract_tool_exposes_full_mia_capabilities() -> None:
    for tool in tool_contracts.CONTRACT_TOOLS:
        payload = tool_contracts.build_tool_summary(tool, tenant="KUKANILEA")
        mia = payload["details"].get("mia")

        assert isinstance(mia, dict)
        assert mia["score"] == mia["max_score"] == len(tool_contracts.MIA_PARITY_CHECKS)
        assert mia["tier"] == "high"

        checks = mia.get("checks") or {}
        assert set(checks.keys()) == set(tool_contracts.MIA_PARITY_CHECKS)
        assert all(checks.values())


def test_mia_parity_matrix_marks_no_current_low_parity_domains() -> None:
    matrix = tool_contracts.build_mia_parity_matrix(tenant="KUKANILEA")

    assert matrix["ok"] is True
    assert matrix["tenant"] == "KUKANILEA"
    assert matrix["checks"] == list(tool_contracts.MIA_PARITY_CHECKS)
    assert matrix["low_parity"] == []
    assert matrix["priority_low_parity"] == []
    assert matrix["baseline_status"] == "parity_aligned"

    rows = matrix["rows"]
    assert len(rows) == len(tool_contracts.CONTRACT_TOOLS)
    for row in rows:
        assert row["score"] == row["max_score"] == len(tool_contracts.MIA_PARITY_CHECKS)
        assert row["tier"] == "high"
