"""Syntactic guardrails for user prompts."""

from __future__ import annotations

import re
from typing import Tuple

SQL_PATTERNS = re.compile(r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE)\b", re.IGNORECASE)
SHELL_PATTERNS = re.compile(r"[;&|`$<>\\]", re.IGNORECASE)
JS_PATTERNS = re.compile(r"<\s*script|javascript:", re.IGNORECASE)
JAILBREAK = re.compile(r"ignore (all |previous )?instructions", re.IGNORECASE)


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
