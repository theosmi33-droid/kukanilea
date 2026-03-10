from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_gemini_doc_mentions_main_only_policy():
    content = _read_text("GEMINI.md").lower()
    assert "main-only policy" in content
    assert "all pull requests must target `main`" in content


def test_contributing_mentions_main_only_base():
    content = _read_text("CONTRIBUTING.md").lower()
    assert "main-only base" in content


def test_main_policy_doc_has_mandatory_rules():
    content = _read_text("docs/policies/MAIN_ONLY_SOURCE_OF_TRUTH.md").lower()
    assert "mandatory rules" in content
    assert "every pull request must target `main`".lower() in content


def test_contributing_mentions_branch_freshness_and_stack_rules():
    content = _read_text("CONTRIBUTING.md").lower()
    assert "main-only freshness" in content
    assert "kein branch-stacking" in content


def test_contributing_mentions_lane_overlap_gate():
    content = _read_text("CONTRIBUTING.md").lower()
    assert "lane overlap" in content
