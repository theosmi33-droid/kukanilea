from __future__ import annotations

from pathlib import Path

CI_WORKFLOW = Path(".github/workflows/ci.yml")


def test_ci_bandit_policy_uses_medium_threshold_by_default() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "BANDIT_SEVERITY_LEVEL: medium" in text
    assert "BANDIT_CONFIDENCE_LEVEL: medium" in text


def test_ci_bandit_policy_enforcement_blocks_nonzero_bandit_exit() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Enforce Bandit policy gate" in text
    assert 'if [ "${{ steps.bandit_scan.outputs.bandit_exit_code }}" != "0" ]; then' in text
    assert "Blocking merge: Bandit findings exceed configured policy threshold" in text
