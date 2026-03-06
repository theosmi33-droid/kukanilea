from __future__ import annotations

import enum
import re
from typing import Iterable, List, Tuple

class ApprovalLevel(enum.IntEnum):
    LEVEL_1_READ_ONLY = 1
    LEVEL_2_VOLATILE = 2
    LEVEL_3_MODIFICATION = 3
    LEVEL_4_DESTRUCTIVE = 4

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

INSTRUCTION_LINE = re.compile(
    r"\b(ignore|override|bypass|system|developer)\b", re.IGNORECASE
)

def detect_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    lowered = text.lower()
    matches: List[str] = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered):
            matches.append(pattern)
    return (len(matches) > 0, matches)

def requires_approval(level: ApprovalLevel) -> bool:
    """Returns True if the given level requires a confirmation gate."""
    return level >= ApprovalLevel.LEVEL_3_MODIFICATION

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
