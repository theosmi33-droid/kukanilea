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
    r"^\s*import\s+httpx\b",
    r"^\s*from\s+httpx\b",
    r"^\s*import\s+urllib\b",
    r"^\s*from\s+urllib\b",
    r"\bos\.system\(",
    r"\beval\(",
    r"\bexec\(",
]


def test_no_forbidden_imports_in_knowledge_email_source() -> None:
    path = Path(__file__).resolve().parents[1] / "app" / "knowledge" / "email_source.py"
    content = path.read_text(encoding="utf-8")
    for pat in FORBIDDEN_PATTERNS:
        assert not re.search(pat, content, flags=re.MULTILINE), pat
