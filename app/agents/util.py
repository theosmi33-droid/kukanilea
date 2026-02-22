from __future__ import annotations

import json
from typing import Any


def hx_trigger(payload: dict[str, Any]) -> dict[str, str]:
    return {"HX-Trigger": json.dumps(payload, ensure_ascii=False)}


def toast_payload(level: str, message: str) -> dict[str, dict[str, str]]:
    return {"toast": {"level": level, "message": message}}
