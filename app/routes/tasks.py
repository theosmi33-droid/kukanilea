from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request, current_app, redirect, url_for
from app.auth import login_required, current_tenant, current_user
from app.security import csrf_protected
from app.contracts.tool_contracts import build_tool_health, build_tool_summary

# Shared logic from core/logic.py (task_list is a core extractor)
from app.core import task_list

logger = logging.getLogger("kukanilea.tasks")
bp = Blueprint("tasks", __name__)

@bp.get("/tasks")
@login_required
def tasks_page():
    from app.modules.projects.logic import ProjectManager

    tenant_id = current_tenant()
    if not tenant_id:
        return redirect(url_for("web.login", next=request.path))

    pm = ProjectManager(current_app.extensions["auth_db"])
    try:
        workspace = pm.ensure_default_hub(tenant_id, actor=current_user() or "system")
        board = workspace["board"]
        bundle = pm.list_tasks(str(board["id"])) or {}
        items = bundle.get("items") or []
        inbox = bundle.get("inbox") or []
        notifications = bundle.get("notifications") or []
    except Exception:
        current_app.logger.exception("Fehler in /tasks")
        items = []
        inbox = []
        notifications = []

    from app.web import _render_base
    return _render_base(
        "tasks.html",
        active_tab="tasks",
        tasks=items,
        inbox=inbox,
        notifications=notifications,
    )

@bp.get("/api/tasks")
@login_required
def api_tasks():
    status = (request.args.get("status") or "OPEN").strip().upper()
    if callable(task_list):
        tasks = task_list(tenant=current_tenant(), status=status, limit=200)  # type: ignore
    else:
        tasks = []
    return jsonify(ok=True, tasks=tasks)

@bp.post("/api/tasks/<task_id>/move")
@login_required
@csrf_protected
def api_task_move(task_id: str):
    payload = request.get_json() or {}
    new_col = payload.get("column")
    if not new_col:
        return jsonify(ok=False), 400
        
    from app.modules.projects.logic import ProjectManager
    pm = ProjectManager(current_app.extensions["auth_db"])
    pm.update_task_column(task_id, new_col)
    
    return jsonify(ok=True)

@bp.get("/api/tasks/summary")
@login_required
def api_tasks_summary():
    tenant = str(current_tenant() or "default")
    return jsonify(build_tool_summary("tasks", tenant=tenant))

@bp.get("/api/tasks/health")
@login_required
def api_tasks_health():
    tenant = str(current_tenant() or "default")
    payload = build_tool_health("tasks", tenant=tenant)
    code = 200 if payload.get("status") in {"ok", "degraded"} else 503
    return jsonify(payload), code
