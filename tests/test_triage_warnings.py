from __future__ import annotations

import sys

from app.devtools.triage import run_cmd_with_warning_detection


def test_warning_detection() -> None:
    result = run_cmd_with_warning_detection(
        [sys.executable, "-c", "import warnings; warnings.warn('test warning')"],
        ignore_regexes=[],
    )
    assert result["warning_count"] > 0
    assert any("test warning" in line.lower() for line in result["warning_lines"])


def test_ignore_regex() -> None:
    result = run_cmd_with_warning_detection(
        [sys.executable, "-c", "import warnings; warnings.warn('test warning')"],
        ignore_regexes=[r"test"],
    )
    assert result["warning_count"] == 0
