from __future__ import annotations

import app.contracts.tool_contracts as contracts


def test_collect_dashboard_summary_marks_single_blocking_degraded_tool(monkeypatch) -> None:
    def _summary(tool: str, tenant: str = "default") -> dict:
        payload = contracts._contract_payload(
            tool=tool,
            status="ok",
            metrics={},
            details={"tenant": tenant},
            tenant=tenant,
        )
        if tool == "upload":
            payload["status"] = "degraded"
            payload["degraded_reason"] = "pending_pipeline_unavailable"
        return payload

    monkeypatch.setattr(contracts, "build_tool_summary", _summary)

    metrics, details, reason = contracts._collect_dashboard_summary("KUKANILEA")

    assert reason == "tool_summary_partial_outage"
    assert metrics["degraded_tools"] == 1
    assert details["degraded"] == ["upload"]
    assert details["degraded_blocking"] == ["upload"]
    assert details["degraded_non_blocking"] == []
    assert details["unavailable_tools"] == ["upload"]


def test_collect_dashboard_summary_tracks_multiple_degraded_tools_without_overstating_unavailability(monkeypatch) -> None:
    def _summary(tool: str, tenant: str = "default") -> dict:
        payload = contracts._contract_payload(
            tool=tool,
            status="ok",
            metrics={},
            details={"tenant": tenant},
            tenant=tenant,
        )
        if tool == "chatbot":
            payload["status"] = "degraded"
            payload["degraded_reason"] = "mia_parity_below_baseline"
        if tool == "tasks":
            payload["status"] = "degraded"
            payload["degraded_reason"] = "tasks_backend_missing"
        return payload

    monkeypatch.setattr(contracts, "build_tool_summary", _summary)

    metrics, details, reason = contracts._collect_dashboard_summary("KUKANILEA")

    assert reason == "tool_summary_partial_outage"
    assert metrics["degraded_tools"] == 2
    assert sorted(details["degraded"]) == ["chatbot", "tasks"]
    assert details["degraded_non_blocking"] == ["chatbot"]
    assert details["degraded_blocking"] == ["tasks"]
    assert details["unavailable_tools"] == ["tasks"]


def test_build_tool_matrix_maps_internal_collector_error_to_degraded_row(monkeypatch) -> None:
    original = contracts.build_tool_summary

    def _summary_with_internal_error(tool: str, tenant: str = "default") -> dict:
        if tool == "email":
            raise RuntimeError("collector exploded")
        return original(tool, tenant)

    monkeypatch.setattr(contracts, "build_tool_summary", _summary_with_internal_error)

    matrix = contracts.build_tool_matrix("KUKANILEA")

    email_row = next(row for row in matrix if row["tool"] == "email")
    assert email_row["status"] == "degraded"
    assert email_row["degraded_reason"] == "summary_aggregation_failed"
    assert email_row["details"]["aggregation_error"] == "internal_error"
    assert email_row["details"]["tenant"] == "KUKANILEA"


def test_collect_dashboard_summary_marks_non_blocking_degradation_without_outage(monkeypatch) -> None:
    def _summary(tool: str, tenant: str = "default") -> dict:
        payload = contracts._contract_payload(
            tool=tool,
            status="ok",
            metrics={},
            details={"tenant": tenant},
            tenant=tenant,
        )
        if tool == "chatbot":
            payload["status"] = "degraded"
            payload["degraded_reason"] = "mia_parity_below_baseline"
        return payload

    monkeypatch.setattr(contracts, "build_tool_summary", _summary)

    metrics, details, reason = contracts._collect_dashboard_summary("KUKANILEA")

    assert reason == "tool_summary_degraded_non_blocking"
    assert metrics["degraded_tools"] == 1
    assert details["degraded"] == ["chatbot"]
    assert details["degraded_non_blocking"] == ["chatbot"]
    assert details["degraded_blocking"] == []
    assert details["unavailable_tools"] == []
