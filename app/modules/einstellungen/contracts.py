from __future__ import annotations

from datetime import UTC, datetime


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(_tenant: str) -> dict:
    return {
        "status": "ok",
        "timestamp": _timestamp(),
        "metrics": {
            "security_headers": 1,
            "admin_tools": 1,
        },
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": 1,
        "offline_safe": 1,
    }
    return payload, 200
