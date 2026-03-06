from __future__ import annotations
import os
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Blueprint, 
    current_app, 
    jsonify, 
    request, 
    render_template, 
    render_template_string,
    redirect, 
    url_for, 
    abort, 
    send_file,
    session,
    g
)
from jinja2 import TemplateNotFound

from .auth import login_required, current_tenant, current_role, current_user, require_role, AuthDB
from .security import csrf_protected, get_csrf_token
from .config import Config
from .rate_limit import login_limiter, chat_limiter
from .errors import json_error
from . import core

logger = logging.getLogger("kukanilea.web")
bp = Blueprint("web", __name__)

# --- Core Context Helpers ---

def _core_get(name: str, default=None):
    return getattr(core, name, default)

def _norm_tenant(t: str) -> str:
    return str(t or "default").strip().lower()

def _audit(action: str, target: str = "-", meta: dict | None = None) -> None:
    from app.core.audit import vault
    vault.log_event(
        tenant_id=_norm_tenant(current_tenant()),
        user=current_user() or "system",
        action=action,
        resource=target,
        details=json.dumps(meta) if meta else "-",
    )

# --- UI Rendering Shared Helpers ---

def _render_base(template_name: str, **kwargs) -> str:
    from app.auth import current_role
    
    branding = Config.get_branding()
    kwargs.setdefault("branding", branding)
    kwargs.setdefault("current_user", current_user())
    kwargs.setdefault("current_role", current_role())
    kwargs.setdefault("current_tenant", current_tenant())
    
    # Non-CDN / Zero-External validation: layout.html handles this.
    
    if isinstance(template_name, str) and "<" in template_name and ">" in template_name:
        probe = template_name.lstrip().lower()
        if probe.startswith("<!doctype") or "<html" in probe:
            return render_template_string(template_name, **kwargs)
        inline_wrapper = "{% extends 'layout.html' %}{% block content %}{{ inline_content|safe }}{% endblock %}"
        return render_template_string(inline_wrapper, inline_content=template_name, **kwargs)

    return render_template(template_name, **kwargs)

def _render_sovereign_tool(tool_key: str, title: str, message: str, active_tab: str = "dashboard") -> str:
    return _render_base(
        "generic_tool.html",
        active_tab=active_tab,
        title=title,
        message=message,
        extra_html=f"<div class='badge'>{tool_key.upper()} bereit</div>",
    )

def _card(kind: str, msg: str) -> str:
    color = "var(--color-success)" if kind == "ok" else "var(--color-danger)"
    return f"<div class='card p-4 border-l-4' style='border-left-color:{color}'>{msg}</div>"

def _is_hx_partial_request() -> bool:
    hx_request = (request.headers.get("HX-Request") or "").lower() == "true"
    hx_history_restore = (request.headers.get("HX-History-Restore-Request") or "").lower() == "true"
    return hx_request and not hx_history_restore

# --- CORE ROUTES (Login, Logout, Home, Admin Shared) ---

@bp.route("/")
def index():
    return redirect(url_for("dashboard.dashboard_page"))

@bp.route("/login", methods=["GET", "POST"])
@login_limiter.limit_required
def login():
    if request.method == "POST":
        # Auth logic is in app/auth.py, here we just handle the view
        pass
    return render_template("login.html")

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))

@bp.route("/health")
def health():
    return jsonify(ok=True, ts=time.time(), app="kukanilea_core_v3")

@bp.route("/admin/forensics")
@login_required
@require_role(["DEV", "ADMIN"])
def admin_forensics():
    from app.core.audit import vault
    from kukanilea_app import measure_db_speed, measure_cpu_usage, measure_memory_usage

    raw_trail = vault.get_audit_trail() or []
    trail = []
    for item in raw_trail:
        d = dict(item or {})
        trail.append({
            "ts": str(d.get("ts") or d.get("created_at") or datetime.utcnow().isoformat()),
            "username": str(d.get("username") or d.get("user") or "system"),
            "action": str(d.get("action") or d.get("event") or "EVENT"),
            "resource": str(d.get("resource") or d.get("doc_id") or d.get("entity_id") or "-"),
            "details": str(d.get("details") or d.get("doc_id") or "-"),
            "tenant_id": str(d.get("tenant_id") or current_tenant() or "SYSTEM"),
        })

    perf = {
        "db_query_speed": measure_db_speed(),
        "cpu_usage": measure_cpu_usage(),
        "memory_info": measure_memory_usage(),
        "boot_time_ms": 420,
    }

    return _render_base(
        "forensic_dashboard.html",
        active_tab="settings",
        trail=trail,
        perf=perf,
        audit_count=len(trail),
    )

@bp.route("/admin/logs")
@login_required
@require_role("DEV")
def admin_logs():
    log_file = Path(current_app.config.get("LOG_DIR", "logs")) / "app.jsonl"
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()[-500:]
                for line in lines:
                    try: logs.append(json.loads(line))
                    except: pass
        except Exception as e:
            logs.append({"timestamp": str(datetime.now()), "level": "ERROR", "message": f"Log read failed: {e}"})
            
    return _render_base("system_logs.html", active_tab="settings", logs=logs)

@bp.route("/admin/audit")
@login_required
@require_role(["DEV", "ADMIN"])
def admin_audit():
    from app.core.audit import vault
    raw_trail = vault.get_audit_trail() or []
    trail = []
    for idx, item in enumerate(raw_trail, start=1):
        d = dict(item or {})
        trail.append({
            "id": d.get("id") or idx,
            "created_at": str(d.get("created_at") or d.get("ts") or datetime.utcnow().isoformat()),
            "tenant_id": str(d.get("tenant_id") or current_tenant() or "SYSTEM"),
            "doc_id": str(d.get("doc_id") or d.get("resource") or "-"),
            "node_hash": str(d.get("node_hash") or d.get("hash") or d.get("event_hash") or "n/a"),
        })
    return _render_base("audit_trail.html", active_tab="settings", trail=trail)

@bp.route("/admin/audit/verify", methods=["POST"])
@login_required
@require_role(["DEV", "ADMIN"])
def admin_audit_verify():
    from app.core.audit import vault
    ok, errors = vault.verify_chain()
    if ok:
        return '<div class="badge pulse" style="background:rgba(16,185,129,0.1); color:var(--color-success); border-color:rgba(16,185,129,0.2);">CHAIN VERIFIZIERT (OK)</div>'
    else:
        return f'<div class="badge" style="background:rgba(239,68,68,0.1); color:var(--color-danger); border-color:rgba(239,68,68,0.2);">CHAIN MANIPULIERT ({len(errors)} FEHLER)</div>'

# Placeholder for db_init if needed by app factory
db_init = None
