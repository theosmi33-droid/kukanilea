from __future__ import annotations

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_MODULE_PATH = Path("scripts/ops/actionable_failures.py")
_SPEC = spec_from_file_location("actionable_failures", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
sys.modules["actionable_failures"] = _MODULE
_SPEC.loader.exec_module(_MODULE)  # type: ignore[arg-type]

FailureRun = _MODULE.FailureRun
build_allowed_branches = _MODULE.build_allowed_branches
filter_actionable_failures = _MODULE.filter_actionable_failures
format_runs = _MODULE.format_runs


def _fixture(name: str) -> Path:
    return Path("tests/fixtures/ops") / name


def _load_runs(name: str) -> list[FailureRun]:
    with _fixture(name).open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return [FailureRun.from_payload(item) for item in payload]


def test_build_allowed_branches_includes_main_and_open_pr_heads() -> None:
    allowed = build_allowed_branches(["codex/active-pr-1", "codex/active-pr-2"])
    assert "main" in allowed
    assert "codex/active-pr-1" in allowed
    assert "codex/active-pr-2" in allowed


def test_build_allowed_branches_normalizes_empty_entries() -> None:
    allowed = build_allowed_branches(["", " ", "codex/active-pr-1"])
    assert "" not in allowed
    assert " " not in allowed
    assert "codex/active-pr-1" in allowed
    assert "main" in allowed


def test_filter_actionable_failures_keeps_main_and_open_pr_failures() -> None:
    runs = _load_runs("failure_runs_sample.json")
    allowed = build_allowed_branches(["codex/active-pr-1"])
    actionable = filter_actionable_failures(runs, allowed)
    ids = [run.database_id for run in actionable]
    assert ids == [1001, 1002]


def test_filter_actionable_failures_empty_when_no_allowed_branch_matches() -> None:
    runs = _load_runs("failure_runs_sample.json")
    actionable = filter_actionable_failures(runs, {"main"})
    ids = [run.database_id for run in actionable]
    assert ids == [1001]


def test_format_runs_contains_branch_workflow_and_url() -> None:
    runs = _load_runs("failure_runs_sample.json")[:1]
    lines = format_runs(runs)
    assert len(lines) == 1
    assert "[main]" in lines[0]
    assert "KUKANILEA CI" in lines[0]
    assert "https://example.invalid/runs/1001" in lines[0]


def test_cli_actionable_mode_uses_fixture_inputs() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/ops/actionable_failures.py",
            "--repo",
            "theosmi33-droid/kukanilea",
            "--limit",
            "50",
            "--failed-runs-json",
            str(_fixture("failure_runs_sample.json")),
            "--open-prs-json",
            str(_fixture("open_pr_heads_sample.json")),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Actionable failed runs (main + open PR branches): 2" in result.stdout
    assert "codex/old-closed-branch" not in result.stdout


def test_cli_actionable_mode_handles_no_open_prs() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/ops/actionable_failures.py",
            "--repo",
            "theosmi33-droid/kukanilea",
            "--limit",
            "50",
            "--failed-runs-json",
            str(_fixture("failure_runs_sample.json")),
            "--open-prs-json",
            str(_fixture("open_pr_heads_empty.json")),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Actionable failed runs (main + open PR branches): 1" in result.stdout
    assert "[main]" in result.stdout
    assert "codex/active-pr-1" not in result.stdout


def test_cli_all_mode_shows_all_entries() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/ops/actionable_failures.py",
            "--all",
            "--failed-runs-json",
            str(_fixture("failure_runs_sample.json")),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "[main]" in result.stdout
    assert "[codex/active-pr-1]" in result.stdout
    assert "[codex/old-closed-branch]" in result.stdout
