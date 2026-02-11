from __future__ import annotations

import subprocess
from pathlib import Path

CONFLICT_MARKERS = ("<<<<<<< ", "=======", ">>>>>>> ")
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "nousage",
    "reports",
    "instance",
    "cleanup_extract",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".sh",
    ".html",
    ".css",
    ".js",
}


def _inside_git_repo() -> bool:
    """Return True when current working tree is a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _scan_text_files_for_markers(root: Path) -> list[str]:
    """Fallback scanner for conflict markers when git is unavailable."""
    hits: list[str] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if file_path.suffix.lower() not in TEXT_SUFFIXES and file_path.name not in {
            ".gitignore",
            "Dockerfile",
        }:
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.startswith(CONFLICT_MARKERS):
                hits.append(f"{rel.as_posix()}:{lineno}:{line}")
    return hits


def test_no_conflict_markers() -> None:
    """Fail when merge conflict markers are present, with git-less fallback."""
    if _inside_git_repo():
        result = subprocess.run(
            [
                "git",
                "grep",
                "-n",
                "-E",
                r"^(<<<<<<< |=======$|>>>>>>> )",
                "--",
                ".",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            raise AssertionError(
                "Conflict markers found:\n" + (result.stdout or result.stderr)
            )
        if result.returncode not in (0, 1):
            raise AssertionError(
                "git grep failed:\n" + (result.stdout or result.stderr)
            )
        return

    hits = _scan_text_files_for_markers(Path.cwd())
    if hits:
        raise AssertionError("Conflict markers found:\n" + "\n".join(hits))
