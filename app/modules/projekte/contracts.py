from __future__ import annotations

from datetime import UTC, datetime

from app import core


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(_tenant: str) -> dict:
    project_list = getattr(core, "project_list", None)
    projects = project_list() if callable(project_list) else []
    return {
        "status": "ok" if callable(project_list) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "total_projects": len(projects),
        },
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": int(payload["status"] == "ok"),
        "offline_safe": 1,
    }
    code = 200 if payload["status"] in {"ok", "degraded"} else 503
    return payload, code



def create_project(*, tenant: str, name: str, description: str = "") -> dict:
    from app.modules.projects.logic import ProjectManager
    from flask import current_app

    manager = ProjectManager(current_app.extensions["auth_db"])
    project_id = manager.create_project(tenant, name, description=description)
    return {"project_id": project_id, "name": (name or "").strip()}
