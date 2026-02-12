from __future__ import annotations

import json
from typing import Any, Dict


def hx_trigger(payload: Dict[str, Any]) -> Dict[str, str]:
    return {"HX-Trigger": json.dumps(payload, ensure_ascii=False)}


def toast_payload(level: str, message: str) -> Dict[str, Dict[str, str]]:
    return {"toast": {"level": level, "message": message}}
