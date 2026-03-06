from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "release_conductor_preflight.sh"


def test_preflight_handles_missing_gh_and_prod_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IEXEC)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["PROD_REPO_PATH"] = str(tmp_path / "missing")
    env["PR_NUMBER"] = "123"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    assert "--- Open PRs" in result.stdout
    assert "[warn] Open PRs failed" in result.stdout
    assert "missing path:" in result.stdout
    assert "Test-Result: NOT_RUN" in result.stdout
    assert "Lane:" in result.stdout
    assert "PR-Link: https://github.com/theosmi33-droid/kukanilea/pull/123" in result.stdout
    assert "Checks: gh=warn, runs=warn, prod=warn" in result.stdout
    # Warnings from optional gh/prod checks must not fail preflight on their own.
    assert result.returncode == 0


def test_preflight_prints_scope_summary() -> None:
    env = os.environ.copy()
    env["PR_NUMBER"] = "777"
    env["LANE"] = "dev-ci"
    env["SCOPE_IN"] = "automation"
    env["SCOPE_OUT"] = "ui"
    env["PROD_REPO_PATH"] = "/no/such/path"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    assert "Lane: dev-ci" in result.stdout
    assert "Scope In: automation" in result.stdout
    assert "Scope Out: ui" in result.stdout
    assert "PR-Link: https://github.com/theosmi33-droid/kukanilea/pull/777" in result.stdout
