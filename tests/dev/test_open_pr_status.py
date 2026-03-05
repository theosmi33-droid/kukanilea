from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


SCRIPT = Path("scripts/dev/open_pr_status.sh")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(extra_env: dict[str, str] | None = None, args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    cmd = ["bash", str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)


def test_open_pr_status_prefers_gh_when_available(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "gh",
        """#!/usr/bin/env bash
if [[ "$1" == "pr" && "$2" == "list" ]]; then
  cat <<'JSON'
[{"number":12,"title":"Improve guard","headRefName":"codex/a","baseRefName":"main","isDraft":false,"mergeStateStatus":"clean"}]
JSON
  exit 0
fi
exit 1
""",
    )

    result = _run(extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"})

    assert result.returncode == 0
    assert "Source: gh" in result.stdout
    assert "Count: 1" in result.stdout
    assert "#12" in result.stdout


def test_open_pr_status_uses_api_fallback_when_gh_fails(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "gh",
        """#!/usr/bin/env bash
exit 1
""",
    )
    _write_executable(
        bin_dir / "curl",
        """#!/usr/bin/env bash
cat <<'JSON'
[{"number":34,"title":"API fallback","head":{"ref":"codex/fallback"},"base":{"ref":"main"},"draft":false,"mergeable_state":"behind"}]
JSON
""",
    )

    result = _run(
        extra_env={
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GH_TOKEN": "dummy-token",
        }
    )

    assert result.returncode == 0
    assert "Source: api" in result.stdout
    assert "Count: 1" in result.stdout
    assert "#34" in result.stdout
    assert "merge=behind" in result.stdout


def test_open_pr_status_returns_2_when_no_gh_and_no_token(tmp_path: Path) -> None:
    # Force PATH without gh/curl wrappers and no tokens -> hard failure.
    result = _run(
        extra_env={
            "PATH": "/usr/bin:/bin",
            "GITHUB_TOKEN": "",
            "GH_TOKEN": "",
        }
    )

    assert result.returncode == 2
    assert "Unable to query PRs for" in result.stderr


def test_open_pr_status_reports_no_open_prs(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "gh",
        """#!/usr/bin/env bash
if [[ "$1" == "pr" && "$2" == "list" ]]; then
  echo "[]"
  exit 0
fi
exit 1
""",
    )

    result = _run(extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"})

    assert result.returncode == 0
    assert "Count: 0" in result.stdout
    assert "No open PRs" in result.stdout


def test_open_pr_status_help() -> None:
    result = _run(args=["--help"])
    assert result.returncode == 0
    assert "Usage: bash scripts/dev/open_pr_status.sh" in result.stdout

