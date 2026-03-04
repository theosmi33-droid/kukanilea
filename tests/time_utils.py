from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Return timezone-aware UTC timestamp in ISO format for deterministic test records."""
    return datetime.now(UTC).isoformat()
