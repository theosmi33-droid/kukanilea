from __future__ import annotations

import pytest

import app.contracts.tool_contracts as contracts


def test_normalize_marks_missing_fields_as_degraded():
    normalized, errors = contracts._normalize_contract_payload({}, "upload")

    assert normalized["tool"] == "upload"
    assert normalized["status"] == "degraded"
    assert "contract_normalized" in normalized["warnings"]
    assert "missing:tool" in errors
    assert "missing:summary" in errors


@pytest.mark.parametrize(
    "payload,error_marker",
    [
        ({"tool": 1, "status": "ok", "ts": "x", "summary": {}, "warnings": [], "links": {}}, "type:tool"),
        ({"tool": "upload", "status": "ok", "ts": 1, "summary": {}, "warnings": [], "links": {}}, "type:ts"),
        ({"tool": "upload", "status": "ok", "ts": "x", "summary": [], "warnings": [], "links": {}}, "type:summary"),
        ({"tool": "upload", "status": "ok", "ts": "x", "summary": {}, "warnings": {}, "links": {}}, "type:warnings"),
    ],
)
def test_normalize_detects_wrong_types(payload, error_marker):
    normalized, errors = contracts._normalize_contract_payload(payload, "upload")

    assert normalized["status"] == "degraded"
    assert error_marker in errors


def test_build_tool_summary_degrades_on_invalid_collector_return(monkeypatch):
    monkeypatch.setitem(contracts.SUMMARY_COLLECTORS, "upload", lambda _tenant: ([], "x", 1))

    payload = contracts.build_tool_summary("upload", tenant="KUKANILEA")

    assert payload["status"] == "degraded"
    assert "collector_contract_invalid" in payload["warnings"]
    assert payload["summary"]["details"]["collector_contract"]["metrics_is_dict"] is False


def test_build_tool_summary_falls_back_to_error_payload_on_exception(monkeypatch):
    monkeypatch.setitem(contracts.SUMMARY_COLLECTORS, "upload", lambda _tenant: 1 / 0)

    payload = contracts.build_tool_summary("upload", tenant="KUKANILEA")

    assert payload["status"] == "error"
    assert payload["summary"]["metrics"]["collector_error"] == 1
    assert "error" in payload["summary"]["details"]
