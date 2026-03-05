from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple

WRITE_VERBS = re.compile(
    r"\b(create|delete|send|update|upload|remove|start|stop|archive|export|revoke|add|modify|schick|sende|lösch|erstelle)\b",
    re.IGNORECASE,
)

UNSAFE_PATTERNS = (
    re.compile(r"(?i)\b(ignore|override|bypass)\b.*\b(instruction|guard|policy|security)\b"),
    re.compile(r"(?i)\b(reveal|show|print)\b.*\b(system\s+prompt|hidden\s+instruction)\b"),
    re.compile(r"(?i)\b(do\s+anything\s+now|dan\s+mode|jailbreak)\b"),
)

READ_PATTERNS = (
    re.compile(r"(?i)^\s*(hallo|hi|hey|moin|servus|guten\s+(morgen|tag|abend))\s*[!.?]*\s*$"),
    re.compile(r"(?i)^\s*(test|funktionierst\s+du\??|bist\s+du\s+da\??|ping)\s*[!.?]*\s*$"),
    re.compile(r"(?i)\b(status|übersicht|zusammenfassung|zeige\s+mir)\b"),
)


@dataclass(frozen=True)
class IntentRisk:
    intent_type: str
    reason: str
    is_write_like: bool


class _SemanticGuard:
    """Optional semantic fallback for write-like intent detection."""

    def is_write_like(self, user_text: str) -> Tuple[bool, str]:
        return False, ""


semantic_guard = _SemanticGuard()


def detect_write_intent(user_text: str) -> bool:
    return classify_intent_risk(user_text).is_write_like


def classify_intent_risk(user_text: str) -> IntentRisk:
    text = str(user_text or "").strip()
    if not text:
        return IntentRisk(intent_type="read", reason="empty_input", is_write_like=False)
    for pattern in UNSAFE_PATTERNS:
        if pattern.search(text):
            return IntentRisk(intent_type="unsafe", reason="unsafe_pattern", is_write_like=True)
    if WRITE_VERBS.search(text):
        return IntentRisk(intent_type="write", reason="write_verb", is_write_like=True)
    for pattern in READ_PATTERNS:
        if pattern.search(text):
            return IntentRisk(intent_type="read", reason="smalltalk_or_status", is_write_like=False)
    ok, _ = semantic_guard.is_write_like(text)
    if ok:
        return IntentRisk(intent_type="write", reason="semantic_guard", is_write_like=True)
    return IntentRisk(intent_type="read", reason="default_read", is_write_like=False)
