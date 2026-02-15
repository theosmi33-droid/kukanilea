from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    r"^\s*import\s+socket\b",
    r"^\s*from\s+socket\b",
    r"^\s*import\s+requests\b",
    r"^\s*from\s+requests\b",
    r"^\s*import\s+httpx\b",
    r"^\s*from\s+httpx\b",
    r"^\s*import\s+urllib\b",
    r"^\s*from\s+urllib\b",
    r"^\s*import\s+watchdog\b",
    r"^\s*from\s+watchdog\b",
    r"^\s*import\s+imaplib\b",
    r"^\s*from\s+imaplib\b",
    r"\bos\.system\(",
    r"\beval\(",
    r"\bexec\(",
]

FORBIDDEN_SUBPROCESS_PATTERNS = [
    r"^\s*import\s+subprocess\b",
    r"^\s*from\s+subprocess\b",
]


def test_autonomy_sources_do_not_use_forbidden_exec_or_network_imports() -> None:
    roots = [
        Path(__file__).resolve().parents[1] / "app" / "autonomy",
        Path(__file__).resolve().parents[1] / "app" / "tags",
    ]
    for root in roots:
        assert root.exists()
        py_files = sorted(root.glob("*.py"))
        assert py_files
        for py in py_files:
            content = py.read_text(encoding="utf-8")
            patterns = list(FORBIDDEN_PATTERNS)
            if py.name != "ocr.py":
                patterns.extend(FORBIDDEN_SUBPROCESS_PATTERNS)
            for pat in patterns:
                assert not re.search(pat, content, flags=re.MULTILINE), (
                    f"{pat} found in {py.name}"
                )
