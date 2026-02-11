from __future__ import annotations

import subprocess

import pytest


def _inside_git_repo() -> bool:
    """Return True when current working tree is a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def test_no_conflict_markers() -> None:
    """Fail on merge markers; skip gracefully outside git working trees."""
    if not _inside_git_repo():
        pytest.skip("not a git repository")

    result = subprocess.run(
        ["git", "grep", "-n", "-E", r"^(<<<<<<< |=======$|>>>>>>> )", "--", "."],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise AssertionError(
            "Conflict markers found:\n" + (result.stdout or result.stderr)
        )
    if result.returncode not in (0, 1):
        raise AssertionError("git grep failed:\n" + (result.stdout or result.stderr))
