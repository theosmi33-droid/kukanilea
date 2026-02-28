from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

def hx_trigger(payload: Dict[str, Any]) -> Dict[str, str]:
    return {"HX-Trigger": json.dumps(payload, ensure_ascii=False)}


def toast_payload(level: str, message: str) -> Dict[str, Dict[str, str]]:
    return {"toast": {"level": level, "message": message}}

def get_soul_directives() -> str:
    """Reads app/agents/config/SOUL.md at runtime."""
    config_path = Path(__file__).parent / "config" / "SOUL.md"
    if config_path.exists():
        return config_path.read_text(encoding="utf-8")
    return "Du bist das KUKANILEA Business Operating System. Verhalte dich hochprofessionell."
