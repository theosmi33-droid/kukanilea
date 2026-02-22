from __future__ import annotations

import os
from typing import Any

from app.crm.core import deals_suggest_next_actions as _fallback_suggestions


def _ai_enabled() -> bool:
    return os.environ.get("KUKA_AI_ENABLE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def deals_suggest_next_actions(tenant_id: str, deal_id: str) -> list[dict[str, Any]]:
    """Gated suggestion provider. Returns deterministic fallback unless AI is enabled."""
    if not _ai_enabled():
        return []
    return _fallback_suggestions(tenant_id=tenant_id, deal_id=deal_id)
