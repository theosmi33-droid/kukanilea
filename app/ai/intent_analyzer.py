from __future__ import annotations

import re
from typing import Tuple

WRITE_VERBS = re.compile(
    r"\b(create|delete|send|update|upload|remove|start|stop|archive|export|revoke|add|modify|schick|sende|lösch|erstelle)\b",
    re.IGNORECASE,
)


class _SemanticGuard:
    """Optional semantic fallback for write-like intent detection."""

    def is_write_like(self, user_text: str) -> Tuple[bool, str]:
        return False, ""


semantic_guard = _SemanticGuard()

STANDARD_REQUEST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("greeting", re.compile(r"\b(hallo|hi|hey|guten\s*(tag|morgen|abend)|servus|moin)\b", re.IGNORECASE)),
    ("self_test", re.compile(r"\b(test|ping|funktionierst\s*du|bist\s*du\s*da|läuft\s*der\s*chat)\b", re.IGNORECASE)),
)


def detect_write_intent(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if WRITE_VERBS.search(text):
        return True
    ok, _ = semantic_guard.is_write_like(text)
    return bool(ok)


def detect_standard_request(user_text: str) -> str:
    text = str(user_text or "").strip()
    if not text:
        return ""
    for label, pattern in STANDARD_REQUEST_PATTERNS:
        if pattern.search(text):
            return label
    return ""
