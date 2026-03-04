from flask import Blueprint, render_template, current_app, json, request, jsonify
from ..auth import login_required, current_tenant
from ..security import csrf_protected
from ..rate_limit import upload_limiter
from app import core
from datetime import datetime
from pathlib import Path
from app.core.malware_scanner import scan_file_stream

bp = Blueprint("upload", __name__)

def _core_get(name: str, default=None):
    return getattr(core, name, default)

def _norm_tenant(t: str) -> str:
    return (t or "default").lower().replace(" ", "_")

def _safe_filename(filename: str) -> str:
    from werkzeug.utils import secure_filename
    return secure_filename(filename)

@bp.get("/upload")
@login_required
def upload_page():
    from ..web import _render_sovereign_tool
    return _render_sovereign_tool(
        "upload",
        "Upload",
        "Upload-Pipeline wird geladen...",
        active_tab="upload",
    )

@bp.post("/upload")
@csrf_protected
@upload_limiter.limit_required
def upload():
    files = request.files.getlist("file")
    if not files:
        return jsonify(error="no_file"), 400
        
    tenant = _norm_tenant(current_tenant() or "default")
    EINGANG = _core_get("EINGANG")
    analyze_to_pending = _core_get("analyze_to_pending") or _core_get("start_background_analysis")
    read_pending = _core_get("read_pending")
    write_pending = _core_get("write_pending")

    # Task 114: Disk Quota Management (100MB limit per tenant for now)
    QUOTA_LIMIT = 100 * 1024 * 1024 
    current_usage = sum(f.stat().st_size for f in (EINGANG / tenant).glob("*") if f.is_file())
    if current_usage > QUOTA_LIMIT:
        return jsonify(error="quota_exceeded", message="Speicherlimit für Mandant erreicht."), 403

    results = []
    from app.core.upload_pipeline import process_upload

    for f in files:
        if not f.filename: continue
        filename = _safe_filename(f.filename)
        
        tenant_in = EINGANG / tenant
        tenant_in.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = tenant_in / f"{ts}__{filename}"
        f.save(dest)
        
        # Phase 5: ClamAV Malware Scan
        if not scan_file_stream(dest):
            dest.unlink()
            return jsonify(error="malware_detected", message="Sicherheitsrisiko erkannt."), 403
        
        is_safe, info = process_upload(dest, tenant)
        if not is_safe:
            current_app.logger.warning(f"Upload rejected: {filename} - {info}")
            continue
            
        token = analyze_to_pending(dest)
        try:
            p = read_pending(token) or {}
            p["tenant"] = tenant
            p["file_hash"] = info
            write_pending(token, p)
        except Exception: pass
        
        results.append({"token": token, "filename": filename})
        
    return jsonify(tokens=results, tenant=tenant)
