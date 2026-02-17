#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FREEZE_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
}
ADR_PREFIXES = ("docs/adr/ADR-", "docs/adr/adr-")


def _staged_files() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    files = _staged_files()
    changed = {str(Path(p)) for p in files}
    touched_freeze = any(path in FREEZE_FILES for path in changed)
    if not touched_freeze:
        return 0

    has_adr = any(
        path.startswith(ADR_PREFIXES) and path.endswith(".md") for path in changed
    )
    if has_adr:
        return 0

    print(
        "[core-freeze] requirements/pyproject were changed without staged ADR.\n"
        "Please add a staged ADR file under docs/adr/ADR-*.md explaining the stack/dependency change.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
