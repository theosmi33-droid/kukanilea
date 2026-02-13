from __future__ import annotations

import sys

from app.devtools.triage import run_cmd_with_warning_detection


def test_non_python_warning_string_not_counted() -> None:
    result = run_cmd_with_warning_detection(
        [
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('Warning: Disk nearly full\\n')",
        ],
        ignore_regexes=[],
    )
    assert result["warning_count"] == 0


def test_python_warning_counted() -> None:
    result = run_cmd_with_warning_detection(
        [sys.executable, "-c", "import warnings; warnings.warn('real warning')"],
        ignore_regexes=[],
    )
    assert result["warning_count"] > 0
    assert any("warning" in line.lower() for line in result["warning_lines"])


def test_ignore_regex_and_sample_cap_are_deterministic() -> None:
    script = "import sys; [sys.stderr.write('x.py:1: DeprecationWarning: w%02d\\n' % i) for i in range(20)]"
    result = run_cmd_with_warning_detection(
        [sys.executable, "-c", script], ignore_regexes=[]
    )
    assert result["warning_count"] == 20
    assert len(result["warning_lines"]) == 10
    assert result["warning_lines"][0].endswith("w00")

    filtered = run_cmd_with_warning_detection(
        [sys.executable, "-c", script],
        ignore_regexes=[r"w0[0-4]$"],
    )
    assert filtered["warning_count"] == 15
    assert all(
        not line.endswith(("w00", "w01", "w02", "w03", "w04"))
        for line in filtered["warning_lines"]
    )
