from __future__ import annotations

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.auth import login_required, require_role, current_tenant
from app.core.tenant_registry import tenant_registry
import os
from pathlib import Path

bp = Blueprint("admin_tenants", __name__, url_prefix="/admin")

@bp.route("/tenants")
@login_required
@require_role("ADMIN")
def list_tenants():
    tenants = tenant_registry.list_tenants()
    return render_template("admin_tenants.html", tenants=tenants, active_tab="settings")

@bp.route("/tenants/add", methods=["POST"])
@login_required
@require_role("ADMIN")
def add_tenant():
    name = (request.form.get("name") or "").strip()
    db_path = (request.form.get("db_path") or "").strip()
    
    if not name or not db_path:
        return '<div style="color: var(--color-danger); font-size: 13px; margin-top: 8px;">Bitte Name und Pfad angeben.</div>'
    
    # 1. Path Validation (Security Guard)
    if not tenant_registry.validate_path(db_path):
        return '<div style="color: var(--color-danger); font-size: 13px; margin-top: 8px;">Ungültiger Pfad oder Dateiendung (nur .db/.sqlite erlaubt).</div>'
    
    path = Path(db_path)
    
    # 2. Existence & Permissions
    if not path.exists():
        return '<div style="color: var(--color-danger); font-size: 13px; margin-top: 8px;">Datenbankdatei nicht gefunden.</div>'
    
    if not os.access(path, os.R_OK | os.W_OK):
        return '<div style="color: var(--color-danger); font-size: 13px; margin-top: 8px;">Keine Lese-/Schreibrechte für diese Datei.</div>'
    
    # 3. ID Generation
    tenant_id = name.lower().replace(" ", "_")
    
    # 4. Save
    if tenant_registry.add_tenant(tenant_id, name, str(path.resolve())):
        return f'<div style="color: var(--color-success); font-size: 13px; margin-top: 8px;">Mandant "{name}" erfolgreich validiert und verknüpft.</div>'
    else:
        return '<div style="color: var(--color-danger); font-size: 13px; margin-top: 8px;">Fehler beim Registrieren des Mandanten.</div>'

@bp.route("/context/switch", methods=["POST"])
@login_required
@require_role("ADMIN")
def switch_context():
    tenant_id = request.form.get("tenant_id")
    if not tenant_id:
        return "", 400
    
    tenant = tenant_registry.get_tenant(tenant_id)
    if not tenant:
        return "Mandant nicht gefunden", 404
    
    # Context Binding
    session["tenant_id"] = tenant_id
    session["tenant_name"] = tenant["name"]
    session["tenant_db_path"] = tenant["db_path"]
    
    # Optional: trigger re-optimization / re-index if needed
    
    # Return empty response with HTMX trigger to reload body
    response = jsonify(ok=True)
    response.headers["HX-Refresh"] = "true"
    return response
