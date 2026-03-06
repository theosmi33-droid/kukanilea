from __future__ import annotations

import re
from pathlib import Path

BACKLOG = Path("tasks/backlog_v1.yaml")
README = Path("tasks/backlog_README.md")
LANES = Path("docs/lanes/LANE_RULES.md")
FLEET = Path("docs/agents/FLEET.md")

TASK_ID_RE = re.compile(r"^- id: (TASK-\d{4})$", re.MULTILINE)
TASK_BLOCK_RE = re.compile(r"(^- id: TASK-\d{4}\n(?:  .*\n)+)", re.MULTILINE)


REQUIRED_KEYS = [
    "title:",
    "lane:",
    "domain:",
    "file_scope:",
    "out_of_scope:",
    "DoD:",
    "tests_to_run:",
    "evidence_required:",
    "risk_level:",
    "rollback_plan:",
    "dependencies:",
    "estimate_minutes:",
]

EXPECTED_LANES = {
    "runtime-ui",
    "security",
    "dev-ci",
    "ops-release",
    "domain-contracts",
    "automation",
    "docs-meta",
}


def _read(path: Path) -> str:
    assert path.exists(), f"Missing expected file: {path}"
    return path.read_text(encoding="utf-8")


def test_backlog_and_support_docs_exist() -> None:
    assert BACKLOG.exists()
    assert README.exists()
    assert LANES.exists()
    assert FLEET.exists()


def test_backlog_contains_at_least_2200_tasks() -> None:
    text = _read(BACKLOG)
    task_ids = TASK_ID_RE.findall(text)
    assert len(task_ids) >= 2200


def test_backlog_task_ids_are_unique() -> None:
    text = _read(BACKLOG)
    task_ids = TASK_ID_RE.findall(text)
    assert len(task_ids) == len(set(task_ids))


def test_top_50_roi_task_range_is_present() -> None:
    text = _read(BACKLOG)
    for n in range(1, 51):
        assert f"TASK-{n:04d}" in text


def test_each_task_block_contains_required_contract_fields() -> None:
    text = _read(BACKLOG)
    blocks = TASK_BLOCK_RE.findall(text)
    assert blocks, "No task blocks found"
    sample = blocks[:200]
    for block in sample:
        for key in REQUIRED_KEYS:
            assert f"  {key}" in block


def test_lane_rules_document_declares_expected_lanes() -> None:
    text = _read(LANES)
    for lane in EXPECTED_LANES:
        assert lane in text


def test_backlog_readme_documents_roi_focus_and_definition_of_done() -> None:
    text = _read(README)
    assert "Top 50 ROI" in text
    assert "Definition of Done" in text
    assert "tests_to_run" in text
