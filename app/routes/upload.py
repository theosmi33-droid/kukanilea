from __future__ import annotations
import logging
import json
import os
import re
from pathlib import Path
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request, render_template, redirect, url_for, abort, send_file

from app.auth import login_required, current_tenant, current_role, current_user
from app.security import csrf_protected
from app.config import Config
from app import core
from app.core.malware_scanner import scan_file_stream
from app.core.upload_pipeline import process_upload
from app.rate_limit import upload_limiter

logger = logging.getLogger("kukanilea.upload")
bp = Blueprint("upload", __name__)

DOCTYPE_CHOICES = [
    "ANGEBOT", "RECHNUNG", "AUFTRAGSBESTAETIGUNG", "AW", "MAHNUNG", "NACHTRAG", "SONSTIGES", "FOTO", "H_RECHNUNG", "H_ANGEBOT"
]

def _core_get(name: str, default=None):
    return getattr(core, name, default)

EINGANG = _core_get("EINGANG")
PENDING_DIR = _core_get("PENDING_DIR")
analyze_to_pending = _core_get("analyze_to_pending")
read_pending = _core_get("read_pending")
write_pending = _core_get("write_pending")
delete_pending = _core_get("delete_pending")
write_done = _core_get("write_done")
read_done = _core_get("read_done")
process_with_answers = _core_get("process_with_answers")

def _norm_tenant(t: str) -> str:
    return str(t or "default").strip().lower()

def _safe_filename(name: str) -> str:
    raw = (name or "").strip().replace("\\", "_").replace("/", "_")
    raw = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._-")
    return raw or "upload"

def _render_base(template_name: str, **kwargs) -> str:
    from app.web import _render_base as web_render_base
    return web_render_base(template_name, **kwargs)

def _render_sovereign_tool(tool_key: str, title: str, message: str, active_tab: str = "upload") -> str:
    from app.web import _render_sovereign_tool as web_render_tool
    return web_render_tool(tool_key, title, message, active_tab=active_tab)

def _wizard_get(p: dict) -> dict:
    w = p.get("wizard") or {}
    for k in ["tenant", "kdnr", "use_existing", "name", "addr", "plzort", "doctype", "document_date"]:
        w.setdefault(k, "")
    return w

def _card(kind: str, msg: str) -> str:
    from app.web import _card as web_card
    return web_card(kind, msg)

@bp.route("/upload", methods=["GET"])
@login_required
def upload_page():
    return _render_sovereign_tool("upload", "Upload", "Upload-Pipeline wird geladen...", active_tab="upload")

@bp.route("/upload", methods=["POST"])
@login_required
@csrf_protected
@upload_limiter.limit_required
def upload():
    files = request.files.getlist("file")
    if not files: return jsonify(error="no_file"), 400
    tenant = _norm_tenant(current_tenant() or "default")
    tenant_eingang = EINGANG / tenant
    tenant_eingang.mkdir(parents=True, exist_ok=True)
    results = []
    for f in files:
        if not f.filename: continue
        filename = _safe_filename(f.filename)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = tenant_eingang / f"{ts}__{filename}"
        f.save(dest)
        if not scan_file_stream(dest):
            dest.unlink()
            return jsonify(error="malware_detected"), 403
        is_safe, info = process_upload(dest, tenant)
        if not is_safe: continue
        token = analyze_to_pending(dest)
        results.append({"token": token, "filename": filename})
    return jsonify(tokens=results, tenant=tenant)

@bp.route("/review/<token>/delete", methods=["POST"])
@login_required
@csrf_protected
def review_delete(token: str):
    delete_pending(token)
    return redirect(url_for("dashboard.dashboard_page"))

@bp.route("/api/progress/<token>")
@login_required
def api_progress(token: str):
    p = read_pending(token)
    if not p: return jsonify(error="not_found"), 404
    return jsonify(status=p.get("status", ""), progress=float(p.get("progress", 0.0) or 0.0))
