from __future__ import annotations
import json
import logging
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, render_template, redirect, url_for
from jinja2 import TemplateNotFound

from app.auth import login_required, current_tenant, current_role, current_user
from app.config import Config
from app import core
from app.core.gewerke_profiles import get_active_profile
from app.modules.dashboard.briefing import latest_briefing

logger = logging.getLogger("kukanilea.dashboard")
bp = Blueprint("dashboard", __name__)

def _core_get(name: str, default=None):
    return getattr(core, name, default)

def _is_hx_partial_request() -> bool:
    hx_request = (request.headers.get("HX-Request") or "").lower() == "true"
    hx_history_restore = (
        request.headers.get("HX-History-Restore-Request") or ""
    ).lower() == "true"
    return hx_request and not hx_history_restore

def _norm_tenant(t: str) -> str:
    return str(t or "default").strip().lower()

def _render_base(template_name: str, **kwargs) -> str:
    from app.web import _render_base as web_render_base
    return web_render_base(template_name, **kwargs)

def _render_sovereign_tool(tool_key: str, title: str, message: str, active_tab: str = "dashboard") -> str:
    from app.web import _render_sovereign_tool as web_render_tool
    return web_render_tool(tool_key, title, message, active_tab=active_tab)

@bp.get("/dashboard")
@login_required
def dashboard_page():
    PENDING_DIR = _core_get("PENDING_DIR")
    if _is_hx_partial_request():
        return _render_sovereign_tool(
            "dashboard",
            "Dashboard",
            "Dashboard-Widgets werden geladen...",
            active_tab="dashboard",
        )
    
    tenant = _norm_tenant(current_tenant() or "default")
    items = []
    if PENDING_DIR and (PENDING_DIR / tenant).exists():
        items = [f.name for f in (PENDING_DIR / tenant).iterdir() if f.is_dir()]
    
    meta = {}
    for token in items:
        m_path = PENDING_DIR / tenant / token / "meta.json"
        if m_path.exists():
            with open(m_path, "r") as f:
                meta[token] = json.load(f)
        else:
            meta[token] = {"filename": "Unbekannt", "status": "PENDING"}

    recent = []
    get_recent = _core_get("get_recent_docs")
    if callable(get_recent):
        recent = get_recent(tenant, limit=6)

    profile = get_active_profile(tenant_id=tenant)
    briefing = latest_briefing()

    return _render_base(
        "dashboard.html",
        active_tab="dashboard",
        items=items,
        meta=meta,
        recent=recent,
        suggestions={"doctypes": profile.get("document_types", [])},
        keywords=profile.get("task_templates", []),
        profile_config=profile,
        briefing=briefing,
    )

@bp.get("/api/system/status")
@login_required
def api_system_status():
    from app.core.observer import get_system_status
    status = get_system_status() or {}
    http_code = int(status.get("http_code") or 200)
    accept = (request.headers.get("Accept") or "").lower()
    wants_html = "text/html" in accept or (request.args.get("format") or "").lower() == "html"
    if wants_html:
        try:
            rendered = render_template("components/system_status.html", **status)
        except TemplateNotFound:
            rendered = render_template("partials/system_status.html", **status)
        return rendered, http_code
    return jsonify(ok=True, status=status), http_code

@bp.get("/api/outbound/status")
@login_required
def api_outbound_status():
    from app.api import outbound_status as _outbound_status
    return _outbound_status()

@bp.post("/api/dashboard/selftest")
@login_required
def api_dashboard_selftest():
    from app.core.selftest import run_selftest
    test_config = {
        "USER_DATA_ROOT": Config.USER_DATA_ROOT,
        "CORE_DB": Config.CORE_DB,
    }
    ok = run_selftest(test_config)
    return jsonify(status="OK" if ok else "ERROR")
