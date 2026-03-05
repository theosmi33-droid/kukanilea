"""Syntactic guardrails for user prompts."""

from __future__ import annotations

import re
from typing import Tuple

SQL_PATTERNS = re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE)\b", re.IGNORECASE)
SHELL_PATTERNS = re.compile(r"[;&|`$<>\\]", re.IGNORECASE)
JS_PATTERNS = re.compile(r"<\s*script|javascript:", re.IGNORECASE)
JAILBREAK = re.compile(
    r"ignore (all |previous )?instructions|"
    r"you are now (dan|developer mode)|"
    r"reveal (the )?(system prompt|hidden instructions)|"
    r"bypass (all )?(security|guardrails?|safety)",
    re.IGNORECASE,
)
WRITE_INTENT = re.compile(
    r"\b(create|delete|update|send|write|ändern|loeschen|löschen|post|execute)\b",
    re.IGNORECASE,
)
UNCERTAIN_INTENT = re.compile(r"\b(maybe|unsure|idk|not sure|egal|whatever|irgendwas)\b", re.IGNORECASE)


def validate_prompt(prompt: str, max_len: int = 500) -> Tuple[bool, str]:
    if not isinstance(prompt, str):
        return False, "Invalid input type"
    if len(prompt) > max_len:
        return False, f"Prompt zu lang (max {max_len} Zeichen)"
    if SQL_PATTERNS.search(prompt):
        return False, "Verbotene SQL-Keywords erkannt"
    if SHELL_PATTERNS.search(prompt):
        return False, "Verbotene Shell-Zeichen erkannt"
    if JS_PATTERNS.search(prompt):
        return False, "Verbotene JavaScript-Patterns erkannt"
    if JAILBREAK.search(prompt):
        return False, "Jailbreak-Attempt erkannt"
    return True, "OK"


def requires_confirm_for_prompt(prompt: str) -> bool:
    """Gate risky prompts; defaults to deny-by-default on uncertain intent."""

    text = str(prompt or "")
    if not text.strip():
        return True
    if UNCERTAIN_INTENT.search(text):
        return True
    return bool(WRITE_INTENT.search(text))
