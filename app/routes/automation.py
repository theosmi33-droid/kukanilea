from __future__ import annotations

import json
import urllib.parse
import ipaddress
import re
from typing import Any
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)

from app import core
from app.auth import current_role, current_tenant, current_user, login_required, require_role
from app.config import Config
from app.modules.automation import (
    automation_rule_create,
    automation_rule_disable,
    automation_rule_get,
    automation_rule_list,
    automation_rule_toggle,
    automation_run_now,
    builder_execution_log_list,
    builder_pending_action_confirm_once,
    builder_pending_action_list,
    builder_pending_action_set_status,
    builder_rule_create,
    builder_rule_get,
    builder_rule_list,
    builder_rule_update,
    generate_daily_insights,
    get_or_build_daily_insights,
    simulate_rule_for_tenant,
)
from app.modules.automation.cron import parse_cron_expression

bp = Blueprint("automation", __name__, url_prefix="/automation")

def init_automation_schema():
    from app.modules.automation import builder_ensure_schema
    try:
        builder_ensure_schema()
    except Exception as e:
        current_app.logger.error(f"Failed to ensure automation schema: {e}")

# Helper from web.py (simplified or copied)
def _render_base(template_name: str, **kwargs) -> str:
    from app.web import _render_base as web_render_base
    return web_render_base(template_name, **kwargs)

def _is_htmx() -> bool:
    return request.headers.get("HX-Request") == "true"

def _automation_error(code: str, message: str, status: int = 400):
    rid = getattr(g, "request_id", "")
    return (
        jsonify(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": {},
                    "request_id": rid,
                },
            }
        ),
        status,
    )

def _automation_read_only_response(api: bool = True):
    rid = getattr(g, "request_id", "")
    if api:
        return jsonify({"ok": False, "error_code": "read_only", "request_id": rid}), 403
    return (
        render_template_string(
            "<h1>Read-only mode</h1><p>Schreibaktionen sind deaktiviert.</p>",
        ),
        403,
    )

def _automation_guard(api: bool = True):
    if bool(current_app.config.get("READ_ONLY", False)):
        return _automation_read_only_response(api=api)
    return None

# --- Routes ---

@bp.get("/rules")
@login_required
@require_role("OPERATOR")
def automation_rules_page():
    rows = automation_rule_list(current_tenant())
    content = render_template(
        "automation/rules.html",
        rules=rows,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")

@bp.get("/rules/new")
@login_required
@require_role("OPERATOR")
def automation_rule_new_page():
    content = render_template(
        "automation/rule_new.html",
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")

@bp.post("/rules/create")
@login_required
@require_role("OPERATOR")
def automation_rule_create_action():
    guarded = _automation_guard(api=not _is_htmx())
    if guarded is not None:
        return guarded
    payload = (
        request.form if not request.is_json else (request.get_json(silent=True) or {})
    )
    try:
        rule_id = automation_rule_create(
            tenant_id=current_tenant(),
            name=str(payload.get("name") or ""),
            scope=str(payload.get("scope") or "leads"),
            condition_kind=str(payload.get("condition_kind") or ""),
            condition_json=str(payload.get("condition_json") or "{}"),
            action_list_json=str(payload.get("action_list_json") or "[]"),
            created_by=current_user() or "system",
        )
    except PermissionError:
        return _automation_read_only_response(api=not _is_htmx())
    except ValueError as exc:
        code = str(exc)
        if code == "db_locked":
            return _automation_error("db_locked", "Datenbank gesperrt.", 503)
        return _automation_error("validation_error", "Regel ungültig.", 400)
    
    if _is_htmx():
        return redirect(url_for("automation.automation_rule_detail_page", rule_id=rule_id))
    return jsonify({"ok": True, "rule_id": rule_id})

@bp.get("/rules/<rule_id>")
@login_required
@require_role("OPERATOR")
def automation_rule_detail_page(rule_id: str):
    row = automation_rule_get(current_tenant(), rule_id)
    if not row:
        return _automation_error("not_found", "Regel nicht gefunden.", 404)
    content = render_template(
        "automation/rule_detail.html",
        rule=row,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")

@bp.get("/pending")
@login_required
@require_role("OPERATOR")
def automation_pending_page():
    items = builder_pending_action_list(tenant_id=current_tenant(), status="pending")
    content = render_template(
        "automation/pending.html",
        items=items,
        read_only=bool(current_app.config.get("READ_ONLY", False)),
    )
    return _render_base(content, active_tab="automation")

@bp.get("/")
@login_required
@require_role("OPERATOR")
def automation_dashboard():
    # Redirect to rules for now or show a summary
    return redirect(url_for("automation.automation_rules_page"))
