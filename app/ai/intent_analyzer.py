from __future__ import annotations

import re
from typing import Tuple

WRITE_VERBS = re.compile(
    r"\b(create|delete|send|start|stop|archive|remove|upload|export|revoke|add|update|modify|schick|sende|lösch|erstelle)\b",
    re.IGNORECASE,
)


class _SemanticGuard:
    """Optional semantic fallback for write-like intent detection."""

    def is_write_like(self, user_text: str) -> Tuple[bool, str]:
        return False, ""


semantic_guard = _SemanticGuard()


def detect_write_intent(user_text: str) -> bool:
    text = str(user_text or "").strip()
    if not text:
        return False
    if WRITE_VERBS.search(text):
        return True
    ok, _ = semantic_guard.is_write_like(text)
    return bool(ok)

