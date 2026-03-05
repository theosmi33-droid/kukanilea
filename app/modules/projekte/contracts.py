from __future__ import annotations

from datetime import UTC, datetime

from app import core

CONTRACT_VERSION = "2026-03-05"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(_tenant: str) -> dict:
    project_list = getattr(core, "project_list", None)
    projects = project_list() if callable(project_list) else []
    status = "ok" if callable(project_list) else "degraded"
    return {
        "tool": "projekte",
        "version": CONTRACT_VERSION,
        "status": status,
        "ts": _timestamp(),
        "summary": {
            "total_projects": len(projects),
            "contract_version": CONTRACT_VERSION,
        },
        "warnings": [] if status == "ok" else ["projects_backend_missing"],
        "links": [{"rel": "health", "href": "/api/projekte/health"}],
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["summary"] = {
        **payload.get("summary", {}),
        "checks": {
            "summary_contract": True,
            "backend_ready": payload["status"] == "ok",
            "offline_safe": True,
        },
    }
    code = 200 if payload["status"] == "ok" else 503
    return payload, code
