from __future__ import annotations
import logging
import json
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app, redirect, url_for
from app.auth import login_required, current_tenant, current_role, require_role, AuthDB
from app.security import csrf_protected
from app.config import Config
from app.errors import json_error
from app.contracts.tool_contracts import build_tool_health, build_tool_summary

logger = logging.getLogger("kukanilea.settings")
bp = Blueprint("settings", __name__)

@bp.post("/settings/branding")
@login_required
@csrf_protected
def settings_branding_save():
    data = request.form
    new_branding = {
        "app_name": data.get("app_name", "KUKANILEA"),
        "primary_color": data.get("primary_color", "#0ea5e9"),
        "footer_text": data.get("footer_text", ""),
    }

    with open(Config.BRANDING_FILE, "w") as f:
        json.dump(new_branding, f, indent=2)
        
    db_path = data.get("core_db_path", "").strip()
    auth_db = current_app.extensions.get("auth_db")
    t_id = current_tenant()
    if auth_db and t_id:
        con = auth_db._db()
        con.execute("UPDATE tenants SET core_db_path = ? WHERE tenant_id = ?", (db_path or None, t_id))
        con.commit()
        con.close()

    return redirect(url_for("settings.settings_page"))

@bp.get("/settings")
@login_required
def settings_page():
    if current_role() not in {"ADMIN", "DEV"}:
        return json_error("forbidden", "Nicht erlaubt.", status=403)
    auth_db: AuthDB = current_app.extensions["auth_db"]

    tenant_db_path = ""
    auth_schema = "unknown"
    auth_tenants = 0
    from app.web import _render_base
    try:
        t_id = current_tenant()
        con = auth_db._db()
        row = con.execute("SELECT core_db_path FROM tenants WHERE tenant_id = ?", (t_id,)).fetchone()
        con.close()
        tenant_db_path = row["core_db_path"] if row else ""
        auth_schema = auth_db.get_schema_version()
        auth_tenants = auth_db.count_tenants()
    except Exception:
        current_app.logger.exception("Settings page fallback activated")

    return _render_base(
        "settings.html",
        active_tab="settings",
        auth_db_path=str(auth_db.path),
        auth_schema=auth_schema,
        auth_tenants=auth_tenants,
        import_root=str(current_app.config.get("IMPORT_ROOT", "")),
        tenant_db_path=tenant_db_path
    )

@bp.route("/legal")
def legal_page():
    from app.web import _render_base
    return _render_base("legal.html", active_tab="settings")

@bp.get("/api/settings/summary")
@login_required
def api_settings_summary():
    tenant = str(current_tenant() or "default")
    return jsonify(build_tool_summary("settings", tenant=tenant))

@bp.get("/api/settings/health")
@login_required
def api_settings_health():
    tenant = str(current_tenant() or "default")
    payload = build_tool_health("settings", tenant=tenant)
    code = 200 if payload.get("status") in {"ok", "degraded"} else 503
    return jsonify(payload), code
