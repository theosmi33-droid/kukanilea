from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TOOL_KEYS: tuple[str, ...] = (
    "dashboard",
    "upload",
    "projects",
    "tasks",
    "messenger",
    "email",
    "calendar",
    "time",
    "visualizer",
    "settings",
    "chatbot",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_summary_contract(tool: str) -> dict[str, Any]:
    if tool not in TOOL_KEYS:
        raise KeyError(tool)

    metrics: dict[str, Any] = {"available": True}
    if tool == "dashboard":
        metrics.update({"tracked_tools": len(TOOL_KEYS), "contracts_ready": len(TOOL_KEYS)})

    return {
        "tool": tool,
        "status": "ok",
        "updated_at": _iso_now(),
        "metrics": metrics,
        "details": {
            "contract": "summary",
            "source": "integration_contracts",
        },
    }


def build_health_contract(tool: str) -> dict[str, Any]:
    if tool not in TOOL_KEYS:
        raise KeyError(tool)

    return {
        "tool": tool,
        "status": "healthy",
        "updated_at": _iso_now(),
        "metrics": {"available": True, "latency_ms": 0},
        "details": {
            "contract": "health",
            "source": "integration_contracts",
            "checks": ["endpoint_reachable"],
        },
    }


def build_dashboard_aggregation() -> dict[str, Any]:
    summaries = {tool: build_summary_contract(tool) for tool in TOOL_KEYS}
    health = {tool: build_health_contract(tool) for tool in TOOL_KEYS}
    degraded = [tool for tool, payload in health.items() if payload.get("status") != "healthy"]
    return {
        "status": "ok" if not degraded else "degraded",
        "updated_at": _iso_now(),
        "metrics": {
            "tool_count": len(TOOL_KEYS),
            "healthy_tools": len(TOOL_KEYS) - len(degraded),
            "degraded_tools": len(degraded),
        },
        "details": {
            "summaries": summaries,
            "health": health,
            "degraded": degraded,
        },
    }
