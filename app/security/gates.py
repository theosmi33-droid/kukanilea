from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

DEFAULT_CONFIRM_TOKENS = frozenset({"CONFIRM", "YES", "TRUE", "1"})

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(?:^|\b)(?:drop|truncate|alter)\s+table\b"),
    re.compile(r"(?i)(?:\bunion\b\s+(?:all\s+)?select\b)"),
    re.compile(r"(?i)(?:'\s*or\s*'1'\s*=\s*'1|\bor\b\s+1\s*=\s*1)"),
    re.compile(r"(?i)(?:--|/\*|\*/|;\s*(?:drop|delete|insert|update|select)\b)"),
    re.compile(r"(?i)<\s*script\b"),
    re.compile(r"(?i)\bjavascript:\s*"),
    re.compile(r"(?i)\bsystem\s+override\b"),
    re.compile(r"(?i)\bignore\s+instructions?\b"),
    re.compile(r"(?i)\bprompt\s+jailbreak\b"),
)


@dataclass(frozen=True)
class InjectionFinding:
    field: str
    value: str
    pattern: str


def confirm_gate(value: str | None, accepted_tokens: Iterable[str] = DEFAULT_CONFIRM_TOKENS) -> bool:
    token = str(value or "").strip().upper()
    normalized = {str(item).strip().upper() for item in accepted_tokens if str(item).strip()}
    return bool(token and token in normalized)


def detect_injection(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def scan_payload_for_injection(payload: Mapping[str, str | None], fields: Iterable[str]) -> InjectionFinding | None:
    for field in fields:
        raw = payload.get(field)
        matched = detect_injection(raw)
        if matched:
            return InjectionFinding(field=field, value=str(raw or ""), pattern=matched)
    return None
