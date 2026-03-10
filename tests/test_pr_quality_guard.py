from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "pr_quality_guard.sh"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def _run_guard(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "--base-branch",
            "main",
        ],
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("seed\n")
    (repo / "docs" / "reviews" / "codex").mkdir(parents=True)
    (repo / "docs" / "reviews" / "codex" / "PR_QUALITY_GUARD_REPORT_20260305.md").write_text("ok\n")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "seed"], repo)
    _run(["git", "checkout", "-b", "codex/20260305-feature"], repo)
    return repo


def test_pr_quality_guard_fails_for_thin_pr(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "small.txt").write_text("tiny\n")
    _run(["git", "add", "small.txt"], repo)
    _run(["git", "commit", "-m", "thin"], repo)

    result = _run_guard(repo)

    assert result.returncode != 0
    assert "MIN_SCOPE gate failed" in result.stdout
    assert "MIN_TESTS gate failed" in result.stdout


def test_pr_quality_guard_passes_for_solid_pr(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    for idx in range(1, 8):
        (repo / f"src_{idx}.txt").write_text("x\n" * 20)

    test_file = repo / "tests" / "test_quality_guard.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        """

def test_a():
    assert True

def test_b():
    assert True

def test_c():
    assert True
""".strip()
        + "\n"
    )

    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "solid"], repo)

    result = _run_guard(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PR_QUALITY_GUARD: PASS" in result.stdout


def test_pr_quality_guard_fails_on_lane_overlap(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    overlap_target = repo / "shared.txt"
    overlap_target.write_text("base\n")
    _run(["git", "add", "shared.txt"], repo)
    _run(["git", "commit", "-m", "add shared"], repo)

    _run(["git", "checkout", "main"], repo)
    _run(["git", "checkout", "-b", "codex/20260305-other"], repo)
    overlap_target.write_text("other branch\n")
    _run(["git", "add", "shared.txt"], repo)
    _run(["git", "commit", "-m", "other touches shared"], repo)

    _run(["git", "checkout", "codex/20260305-feature"], repo)
    overlap_target.write_text("feature branch\n")
    for idx in range(1, 7):
        (repo / f"scope_{idx}.txt").write_text("scope\n" * 40)
    test_file = repo / "tests" / "test_overlap_guard.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("\n".join([f"def test_{i}():\n    assert True" for i in range(6)]) + "\n")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "feature touches shared too"], repo)

    result = _run_guard(repo)

    assert result.returncode != 0
    assert "Lane overlap check failed" in result.stdout


def test_pr_quality_guard_fails_on_stacked_codex_branch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    _run(["git", "checkout", "main"], repo)
    _run(["git", "checkout", "-b", "codex/20260305-other"], repo)
    (repo / "other_scope.txt").write_text("other\n")
    _run(["git", "add", "other_scope.txt"], repo)
    _run(["git", "commit", "-m", "other scope change"], repo)

    _run(["git", "checkout", "codex/20260305-feature"], repo)
    _run(["git", "merge", "--no-ff", "--no-edit", "codex/20260305-other"], repo)

    result = _run_guard(repo)

    assert result.returncode != 0
    assert "Branch context gate failed" in result.stdout
