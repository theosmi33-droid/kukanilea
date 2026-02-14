from __future__ import annotations

import re
from pathlib import Path

TARGETS = [
    "app/lead_intake",
    "app/entity_links",
    "app/automation",
    "app/knowledge",
    "app/web.py",
]

FORBIDDEN_PATTERNS = [
    r"^\s*import\s+subprocess\b",
    r"^\s*from\s+subprocess\b",
    r"^\s*import\s+socket\b",
    r"^\s*from\s+socket\b",
    r"^\s*import\s+requests\b",
    r"^\s*from\s+requests\b",
    r"\bos\.system\(",
    r"\beval\(",
    r"\bexec\(",
]


def test_forbidden_imports_absent_in_sensitive_modules() -> None:
    root = Path(__file__).resolve().parents[1]
    files: list[Path] = []
    for rel in TARGETS:
        path = root / rel
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))

    assert files, "No files found for forbidden-imports scan"

    violations: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, content, flags=re.MULTILINE):
                violations.append(f"{file_path.relative_to(root)} -> {pat}")

    assert not violations, "forbidden patterns found:\n" + "\n".join(violations)
