from pathlib import Path


def test_pr_guard_jobs_do_not_have_pr_only_job_level_condition() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    pr_guard_block = workflow.split("pr-quality-guard:", 1)[1].split("ui-conflict-guard:", 1)[0]
    assert "if: github.event_name == 'pull_request'" not in pr_guard_block.split("steps:", 1)[0]
    assert "if: github.event_name == 'pull_request'" in pr_guard_block

    ui_guard_block = workflow.split("ui-conflict-guard:", 1)[1].split("quality-gates:", 1)[0]
    assert "if: github.event_name == 'pull_request'" not in ui_guard_block.split("steps:", 1)[0]
    assert "if: github.event_name == 'pull_request'" in ui_guard_block


def test_quality_gates_still_wait_for_guard_jobs() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    quality_block = workflow.split("quality-gates:", 1)[1].split("test:", 1)[0]
    assert "needs: [pr-quality-guard, ui-conflict-guard]" in quality_block
