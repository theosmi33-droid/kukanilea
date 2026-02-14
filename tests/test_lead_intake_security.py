from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    r"^\s*import\s+subprocess\b",
    r"^\s*from\s+subprocess\b",
    r"^\s*import\s+socket\b",
    r"^\s*from\s+socket\b",
    r"^\s*import\s+requests\b",
    r"^\s*from\s+requests\b",
    r"^\s*import\s+urllib\b",
    r"^\s*from\s+urllib\b",
    r"^\s*import\s+httpx\b",
    r"^\s*from\s+httpx\b",
    r"\bos\.system\(",
    r"\beval\(",
    r"\bexec\(",
    r"^\s*import\s+ctypes\b",
    r"^\s*from\s+ctypes\b",
    r"^\s*import\s+pty\b",
    r"^\s*from\s+pty\b",
    r"^\s*import\s+shlex\b",
    r"^\s*from\s+shlex\b",
]


def test_no_forbidden_imports_or_exec_in_lead_intake_sources() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "lead_intake"
    assert root.exists()
    for py in sorted(root.glob("*.py")):
        content = py.read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATTERNS:
            assert not re.search(pat, content, flags=re.MULTILINE), (
                f"{pat} found in {py.name}"
            )
