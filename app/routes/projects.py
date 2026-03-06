from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request, current_app, redirect, url_for
from app.auth import login_required, current_tenant, current_user
from app.security import csrf_protected
from app.contracts.tool_contracts import build_tool_health, build_tool_summary

logger = logging.getLogger("kukanilea.projects")
bp = Blueprint("projects", __name__)

@bp.route("/projects")
@login_required
def projects_list():
    from app.modules.projects.logic import ProjectManager

    pm = ProjectManager(current_app.extensions["auth_db"])
    tenant_id = current_tenant()
    if not tenant_id:
        current_app.logger.warning("/projects called without tenant in session")
        return redirect(url_for("web.login", next=request.path))

    from app.web import _render_base
    try:
        workspace = pm.ensure_default_hub(tenant_id, actor=current_user() or "system")
        project = workspace["project"]
        board = workspace["board"]
        board_id = str(board["id"])
        boards = pm.list_boards(tenant_id=tenant_id, project_id=str(project["id"]))
        board_state = pm.list_board_state(tenant_id=tenant_id, board_id=board_id)
        columns = board_state.get("columns") or workspace.get("columns") or []
        cards = board_state.get("cards") or []
        activities = board_state.get("activities") or []
    except Exception:
        current_app.logger.exception("Fehler in /projects")
        return _render_base(
            "<div class='card p-4'><h2>Projekte konnten nicht geladen werden</h2><p class='muted mt-2'>Leerer Zustand wird angezeigt, bis die Projekt-Daten wieder verfügbar sind.</p></div>",
            active_tab="projects",
        )

    tasks = pm.list_tasks(board_id)
    return _render_base(
        "kanban.html",
        active_tab="projects",
        project=project,
        board=board,
        boards=boards,
        columns=columns,
        cards=cards,
        activities=activities,
        tasks=tasks,
    )

@bp.get("/api/projects/summary")
@login_required
def api_projects_summary():
    tenant = str(current_tenant() or "default")
    return jsonify(build_tool_summary("projects", tenant=tenant))

@bp.get("/api/projects/health")
@login_required
def api_projects_health():
    tenant = str(current_tenant() or "default")
    payload = build_tool_health("projects", tenant=tenant)
    code = 200 if payload.get("status") in {"ok", "degraded"} else 503
    return jsonify(payload), code
