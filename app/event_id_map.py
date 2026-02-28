from __future__ import annotations

import hashlib


def entity_id_int(text_id: str) -> int:
    """Map a stable text identifier to deterministic positive int64."""
    raw = hashlib.sha256((text_id or "").encode("utf-8")).digest()
    value = int.from_bytes(raw[:8], byteorder="big", signed=False) & ((1 << 63) - 1)
    return value or 1
