from __future__ import annotations

from pathlib import Path


def test_roi_blueprint_document_exists_and_is_non_empty():
    doc_path = Path("docs/product/ROI_BLUEPRINT.md")
    assert doc_path.exists()
    text = doc_path.read_text(encoding="utf-8").strip()
    assert len(text) > 500


def test_roi_blueprint_keeps_core_sections_and_metrics():
    text = Path("docs/product/ROI_BLUEPRINT.md").read_text(encoding="utf-8")
    assert "Top 10 Pain Points & Solutions" in text
    assert "The 3 Killer Flows" in text
    assert "Instrumentation Metrics" in text
    assert "Acceptance Criteria (AC)" in text
    assert "Do-Not-Do (Scope Killers)" in text
    for metric in ("TFR", "QCT", "DSO", "TTC"):
        assert metric in text
