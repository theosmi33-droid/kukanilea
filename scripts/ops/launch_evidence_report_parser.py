#!/usr/bin/env python3
"""Parser for launch evidence gate JSON reports."""

from __future__ import annotations

import json
from pathlib import Path


def load_report(path: str | Path) -> dict:
    report_path = Path(path)
    return json.loads(report_path.read_text(encoding="utf-8"))


def expected_exit_code(report: dict) -> int:
    fail_count = int(report.get("counts", {}).get("fail", 0))
    warn_count = int(report.get("counts", {}).get("warn", 0))
    if fail_count > 0:
        return 3
    if warn_count > 0:
        return 2
    return 0


def is_valid_report(report: dict) -> bool:
    required_keys = {"timestamp", "decision", "exit_code", "counts", "gates"}
    if not required_keys.issubset(report):
        return False
    counts = report["counts"]
    if not {"pass", "warn", "fail"}.issubset(counts):
        return False
    return isinstance(report["gates"], list)
