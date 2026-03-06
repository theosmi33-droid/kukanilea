from __future__ import annotations

import json
from pathlib import Path

FLOWS_MD = Path("gemini_prompt_2_mia_flows.md")
FLOWS_JSON = Path("gemini_prompt_2_mia_flows_summary.json")


def _read(path: Path) -> str:
    assert path.exists(), f"missing: {path}"
    return path.read_text(encoding="utf-8")


def _load_summary() -> dict:
    return json.loads(_read(FLOWS_JSON))


def test_flow_artifacts_exist() -> None:
    assert FLOWS_MD.exists()
    assert FLOWS_JSON.exists()


def test_summary_declares_25_cross_tool_flows() -> None:
    summary = _load_summary()
    assert summary.get("total_flows") == 25
    assert len(summary.get("flows", [])) == 25


def test_summary_lists_core_business_tools() -> None:
    summary = _load_summary()
    tools = set(summary.get("tools_involved", []))
    required = {"Email", "ERP", "Tasks", "Calendar", "Messaging", "DMS"}
    assert required.issubset(tools)


def test_each_flow_has_confirm_gate_and_recovery_strategy() -> None:
    summary = _load_summary()
    for flow in summary["flows"]:
        assert "confirm_gate_required" in flow
        assert flow.get("recovery_strategy") == "fallback_or_escalation"


def test_markdown_contains_25_numbered_sections() -> None:
    text = _read(FLOWS_MD)
    section_count = 0
    for idx in range(1, 26):
        if f"## {idx})" in text:
            section_count += 1
    assert section_count == 25


def test_markdown_documents_confirm_gate_and_audit_events() -> None:
    text = _read(FLOWS_MD)
    assert "Confirm-Gates" in text
    assert "Audit Events" in text


def test_flow_ids_are_unique_and_dense() -> None:
    summary = _load_summary()
    ids = [flow["id"] for flow in summary["flows"]]
    assert len(ids) == len(set(ids))
    assert ids[0] == "flow_01"
    assert ids[-1] == "flow_25"
