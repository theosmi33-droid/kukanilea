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
from app.core.upload_pipeline import process_upload, save_upload_stream
from app.core.gewerke_profiles import get_active_profile
from app.contracts.tool_contracts import build_tool_health, build_tool_summary
from app.modules.upload.document_processing import register_document_upload, run_virus_scan_hook
from app.modules.upload.ingestion import ingest_unstructured_bytes
from app.rate_limit import upload_limiter

logger = logging.getLogger("kukanilea.upload")
bp = Blueprint("upload", __name__)

def _core_get(name: str, default=None):
    return getattr(core, name, default)

EINGANG = _core_get("EINGANG")
PENDING_DIR = _core_get("PENDING_DIR")
BASE_PATH = _core_get("BASE_PATH")
DONE_DIR = _core_get("DONE_DIR")
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

def _profile_for_current_tenant() -> dict:
    tenant = _norm_tenant(current_tenant() or "default")
    return get_active_profile(tenant_id=tenant)


def _doctype_choices() -> list[str]:
    profile = _profile_for_current_tenant()
    values = profile.get("document_types") or []
    choices = [str(v).strip().upper() for v in values if str(v or "").strip()]
    return choices or ["SONSTIGES"]


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

def _wizard_save(token: str, p: dict, w: dict) -> None:
    p["wizard"] = w
    write_pending(token, p)

def _card(kind: str, msg: str) -> str:
    from app.web import _card as web_card
    return web_card(kind, msg)

@bp.route("/upload", methods=["GET"])
@login_required
def upload_page():
    return _render_sovereign_tool(
        "upload",
        "Upload",
        "Upload-Pipeline wird geladen...",
        active_tab="upload",
    )

@bp.route("/upload", methods=["POST"])
@login_required
@csrf_protected
@upload_limiter.limit_required
def upload():
    files = request.files.getlist("file")
    if not files:
        return jsonify(error="no_file"), 400
        
    tenant = _norm_tenant(current_tenant() or "default")
    QUOTA_LIMIT = 100 * 1024 * 1024 
    
    tenant_eingang = EINGANG / tenant
    tenant_eingang.mkdir(parents=True, exist_ok=True)
    
    current_usage = sum(f.stat().st_size for f in tenant_eingang.glob("*") if f.is_file())
    if current_usage > QUOTA_LIMIT:
        return jsonify(error="quota_exceeded", message="Speicherlimit für Mandant erreicht."), 403

    results = []
    for f in files:
        if not f.filename: continue
        filename = _safe_filename(f.filename)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = tenant_eingang / f"{ts}__{filename}"
        try:
            save_upload_stream(f, dest)
        except ValueError as exc:
            if str(exc) == "file_too_large":
                try:
                    dest.unlink(missing_ok=True)
                except Exception:
                    pass
                return jsonify(error="file_too_large", message="Datei ist zu gross."), 413
            return jsonify(error="invalid_upload_stream"), 400
        
        result = process_upload(dest, tenant)
        if not result.success:
            current_app.logger.warning("Upload rejected: %s - %s", filename, result.error_message)
            continue

        hook_clean, hook_reason = run_virus_scan_hook(dest, tenant)
        if not hook_clean:
            current_app.logger.warning("Upload rejected by virus scan hook: %s (%s)", filename, hook_reason)
            try:
                dest.unlink(missing_ok=True)
            except Exception:
                pass
            continue
            
        token = analyze_to_pending(dest)
        try:
            p = read_pending(token) or {}
            p["tenant"] = tenant
            p["file_hash"] = result.file_hash
            write_pending(token, p)
        except Exception: pass

        try:
            register_document_upload(file_path=dest, tenant_id=tenant, file_hash=str(result.file_hash or ""))
        except Exception as exc:
            current_app.logger.warning("Document processing registration failed for %s: %s", filename, exc)
        
        results.append({"token": token, "filename": filename})
        
    return jsonify(tokens=results, tenant=tenant)

@bp.route("/review/<token>/delete", methods=["POST"])
@login_required
@csrf_protected
def review_delete(token: str):
    try:
        delete_pending(token)
    except Exception: pass
    return redirect(url_for("dashboard.dashboard_page"))

@bp.route("/review/<token>/kdnr", methods=["GET", "POST"])
@login_required
@csrf_protected
def review(token: str):
    p = read_pending(token)
    if not p:
        return _render_base(_card("error", "Nicht gefunden."), active_tab="upload")
    
    profile = _profile_for_current_tenant()

    if p.get("status") == "ANALYZING":
        return _render_base(
            "review.html",
            active_tab="upload",
            token=token,
            filename=p.get("filename", ""),
            is_pdf=True,
            is_text=False,
            preview=None,
            w=_wizard_get(p),
            doctypes=_doctype_choices(),
            kdnr_ranked=[],
            name_suggestions=[],
            suggested_doctype="SONSTIGES",
            suggested_date="",
            confidence=0,
            msg="Analyse läuft noch. Bitte kurz warten oder zurück zur Übersicht."
        )

    w = _wizard_get(p)
    w["tenant"] = _norm_tenant(current_tenant() or p.get("tenant", "") or "default")

    if request.method == "POST":
        # Handle review submission logic from web.py if needed, 
        # but keep it simple for now or delegate back to web.py if too complex.
        pass

    doctype_choices = _doctype_choices()
    suggested_doctype = (p.get("doctype_suggested") or "SONSTIGES").upper()
    if not w.get("doctype"):
        w["doctype"] = suggested_doctype if suggested_doctype in doctype_choices else "SONSTIGES"
    
    suggested_date = (p.get("doc_date_suggested") or "").strip()
    confidence = 40
    if suggested_doctype and suggested_doctype != "SONSTIGES": confidence += 20
    if suggested_date: confidence += 20

    return _render_base(
        "review.html",
        active_tab="upload",
        token=token,
        filename=p.get("filename", ""),
        is_pdf=True,
        is_text=False,
        preview=None,
        w=w,
        doctypes=doctype_choices,
        kdnr_ranked=p.get("kdnr_ranked", []),
        name_suggestions=p.get("name_suggestions", []),
        suggested_doctype=suggested_doctype,
        suggested_date=suggested_date,
        confidence=confidence,
        required_fields=profile.get("required_fields", []),
        profile=profile,
    )

@bp.route("/done/<token>")
@login_required
def done_view(token: str):
    d = read_done(token) or {}
    fp = d.get("final_path", "")
    return _render_base("done.html", active_tab="upload", final_path=fp)

@bp.route("/api/progress")
@login_required
def api_progress_multi():
    tokens = request.args.get("tokens", "").split(",")
    results = {}
    for t in tokens:
        if not t: continue
        p = read_pending(t)
        if p:
            results[t] = {
                "status": p.get("status", "ANALYZING"),
                "progress": p.get("progress", 0),
                "progress_phase": p.get("progress_phase", "")
            }
        else:
            results[t] = {"status": "NOT_FOUND", "progress": 0}
    return jsonify(results)

@bp.route("/api/progress/<token>")
@login_required
def api_progress(token: str):
    p = read_pending(token)
    if not p:
        return jsonify(error="not_found"), 404
    return jsonify(
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", ""),
    )


@bp.route("/api/upload/ingest", methods=["POST"])
@login_required
@upload_limiter.limit_required
def api_upload_ingest():
    tenant = _norm_tenant(current_tenant() or "default")
    body = request.get_json(silent=True) if request.is_json else None

    source = "text"
    raw_text = ""
    metadata: dict = {}
    if isinstance(body, dict):
        source = str(body.get("source") or "text")
        raw_text = str(body.get("text") or body.get("transcript") or "")
        metadata = dict(body.get("metadata") or {}) if isinstance(body.get("metadata"), dict) else {}
    else:
        source = str(request.form.get("source") or "text")
        raw_text = str(request.form.get("text") or request.form.get("transcript") or "")
        metadata = {}

    file_storage = request.files.get("file") if request.files else None
    if file_storage is not None and file_storage.filename:
        source = str(request.form.get("source") or Path(file_storage.filename).suffix.lstrip(".") or source)
        file_bytes = file_storage.read()
        metadata["filename"] = file_storage.filename
        metadata["content_type"] = str(file_storage.content_type or "")
        payload_bytes = file_bytes
        filename = str(file_storage.filename or "")
        content_type = str(file_storage.content_type or "")
    else:
        payload_bytes = raw_text.encode("utf-8")
        filename = str(metadata.get("filename") or "")
        content_type = str(metadata.get("content_type") or "")

    try:
        payload = ingest_unstructured_bytes(
            source=source,
            tenant=tenant,
            payload_bytes=payload_bytes,
            metadata=metadata,
            filename=filename,
            content_type=content_type,
        )
    except ValueError as exc:
        if str(exc) == "quota_exceeded":
            return jsonify(error="quota_exceeded", message="Speicherlimit für Mandant erreicht."), 403
        raise
    return jsonify(payload), 200


@bp.route("/api/upload/summary", methods=["GET"])
@login_required
def api_upload_summary():
    tenant = str(current_tenant() or "default")
    return jsonify(build_tool_summary("upload", tenant=tenant))


@bp.route("/api/upload/health", methods=["GET"])
@login_required
def api_upload_health():
    tenant = str(current_tenant() or "default")
    payload = build_tool_health("upload", tenant=tenant)
    code = 200 if payload.get("status") in {"ok", "degraded"} else 503
    return jsonify(payload), code
