from __future__ import annotations

import json
from pathlib import Path


FLOWS_SUMMARY = Path("gemini_prompt_2_mia_flows_summary.json")
GUARDRAILS_DOC = Path("docs/security/MIA_GUARDRAILS.md")
REGISTRY_DOC = Path("docs/ai/action_registry.md")


ROI_KEYWORDS = (
    "angebot",
    "mahn",
    "kosten",
    "wartungsverträge",
    "nachtrag",
    "cockpit",
)


def _load_flows() -> list[dict]:
    payload = json.loads(FLOWS_SUMMARY.read_text(encoding="utf-8"))
    return payload["flows"]


def test_mia_flows_keep_confirm_and_audit_coverage() -> None:
    flows = _load_flows()
    confirm_required = 0
    for flow in flows:
        if flow.get("confirm_gate_required"):
            confirm_required += 1
        audit_categories = flow.get("audit_event_categories") or []
        assert len(audit_categories) >= 3
    assert confirm_required >= 20


def test_mia_has_multiple_roi_relevant_flows() -> None:
    names = [str(flow.get("name", "")).lower() for flow in _load_flows()]
    roi_hits = [name for name in names if any(keyword in name for keyword in ROI_KEYWORDS)]
    assert len(roi_hits) >= 5


def test_guardrails_doc_describes_hardened_layers() -> None:
    text = GUARDRAILS_DOC.read_text(encoding="utf-8").lower()
    for marker in (
        "untrusted input",
        "pre-intent guardrail",
        "pre-execution guardrail",
        "confirm-gate",
        "audit",
        "block",
        "route_to_review",
    ):
        assert marker in text


def test_registry_doc_mentions_scale_readiness() -> None:
    text = REGISTRY_DOC.read_text(encoding="utf-8").lower()
    assert "large action inventories" in text
    assert "search/filter actions" in text
