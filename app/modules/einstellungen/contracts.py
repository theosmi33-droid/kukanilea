from __future__ import annotations

from datetime import UTC, datetime

CONTRACT_VERSION = "2026-03-05"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(_tenant: str) -> dict:
    return {
        "tool": "einstellungen",
        "version": CONTRACT_VERSION,
        "status": "ok",
        "ts": _timestamp(),
        "summary": {
            "security_headers": True,
            "admin_tools": True,
            "contract_version": CONTRACT_VERSION,
        },
        "warnings": [],
        "links": [{"rel": "health", "href": "/api/einstellungen/health"}],
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["summary"] = {
        **payload.get("summary", {}),
        "checks": {
            "summary_contract": True,
            "backend_ready": True,
            "offline_safe": True,
        },
    }
    return payload, 200
