from __future__ import annotations
from datetime import UTC, datetime
from app.agents.orchestrator import Orchestrator

def _timestamp() -> str:
    return datetime.now(UTC).isoformat()

def build_summary(tenant: str) -> dict:
    # Basic availability check for orchestrator
    try:
        Orchestrator()
        active = True
    except Exception:
        active = False
        
    return {
        "status": "ok" if active else "error",
        "timestamp": _timestamp(),
        "metrics": {
            "orchestrator_ready": int(active),
            "local_llm_ready": 1,
        },
    }

def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": payload["metrics"]["orchestrator_ready"],
        "offline_safe": 1,
    }
    code = 200 if payload["status"] == "ok" else 503
    return payload, code
