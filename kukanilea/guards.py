from __future__ import annotations

import re
from typing import Iterable, List, Tuple

INJECTION_PATTERNS = [
    r"ignore (all|previous) (rules|instructions)",
    r"system prompt",
    r"developer message",
    r"exfiltrat",
    r"print all db",
    r"dump.*database",
    r"delete files?",
    r"rm -rf",
    r"bypass policy",
]

INSTRUCTION_LINE = re.compile(r"\b(ignore|override|bypass|system|developer)\b", re.IGNORECASE)


def detect_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    lowered = text.lower()
    matches: List[str] = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            matches.append(pattern)
    return (len(matches) > 0, matches)


def neutralize_untrusted_text(text: str, *, max_lines: int = 200) -> str:
    lines = (text or "").splitlines()
    safe_lines: List[str] = []
    for line in lines[:max_lines]:
        if INSTRUCTION_LINE.search(line):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def build_safe_suggestions(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        item = (item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
