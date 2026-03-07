from __future__ import annotations

from app.contracts.tool_contracts import build_contract_response
from app import core


def build_summary(tenant: str) -> dict:
    project_list = getattr(core, "project_list", None)
    projects = project_list() if callable(project_list) else []
    status = "ok" if callable(project_list) else "degraded"
    degraded_reason = "projects_backend_missing" if status == "degraded" else ""
    return build_contract_response(
        tool="projekte",
        status=status,
        degraded_reason=degraded_reason,
        metrics={
            "total_projects": len(projects),
        },
        details={
            "source": "core.project_list",
        },
        tenant=tenant,
    )


def build_health(tenant: str) -> tuple[dict, int]:
    summary = build_summary(tenant)
    return build_health_response(
        tool="projekte",
        status=summary["status"],
        metrics=summary["metrics"],
        details=summary["details"],
        tenant=tenant,
        degraded_reason=summary.get("degraded_reason", ""),
        checks={
            "summary_contract": True,
            "backend_ready": summary.get("status") == "ok",
            "offline_safe": True,
        },
    )



def create_project(*, tenant: str, name: str, description: str = "") -> dict:
    from app.modules.projects.logic import ProjectManager
    from flask import current_app

    manager = ProjectManager(current_app.extensions["auth_db"])
    project_id = manager.create_project(tenant, name, description=description)
    return {"project_id": project_id, "name": (name or "").strip()}
