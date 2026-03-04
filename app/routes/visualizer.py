from __future__ import annotations
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app

from app.auth import login_required, current_tenant
from app.web import _render_base, _render_sovereign_tool, _is_hx_partial_request, _unb64, _is_allowed_path, _b64
from app import core

logger = logging.getLogger("kukanilea.visualizer")
bp = Blueprint("visualizer", __name__)

VISUALIZER_EXTS = {".pdf", ".xlsx", ".csv"}

def _core_get(name: str, default=None):
    return getattr(core, name, default)

list_pending = _core_get("list_pending")
list_recent_docs = _core_get("list_recent_docs")
build_visualizer_payload = _core_get("build_visualizer_payload")
EINGANG = _core_get("EINGANG")

def _visualizer_item_from_path(path: Path, source: str = "vault") -> dict | None:
    try:
        rp = path.resolve()
    except Exception: return None
    if not rp.exists() or not rp.is_file(): return None
    ext = rp.suffix.lower()
    if ext not in VISUALIZER_EXTS: return None
    if not _is_allowed_path(rp): return None
    try:
        st = rp.stat()
        return {
            "id": _b64(str(rp)),
            "name": rp.name,
            "path": str(rp),
            "ext": ext,
            "size": int(st.st_size),
            "updated_at": Path(rp).stat().st_mtime,
            "source": source,
        }
    except Exception: return None

def _collect_visualizer_items(tenant: str, limit: int = 80) -> list:
    items = []
    seen = set()
    
    def add_p(p: Path, s: str):
        try:
            k = str(p.resolve())
            if k in seen: return
            item = _visualizer_item_from_path(p, source=s)
            if item:
                items.append(item)
                seen.add(k)
        except Exception: pass

    for p_info in (list_pending() or []):
        raw = p_info.get("path", "")
        if raw: add_p(Path(raw), "pending")

    if callable(list_recent_docs):
        try:
            for row in list_recent_docs(tenant_id=tenant, limit=limit*2) or []:
                raw = row.get("file_path") or ""
                if raw: add_p(Path(raw), "archive")
        except Exception: pass

    tenant_in = EINGANG / tenant
    if tenant_in.exists():
        for fp in sorted(tenant_in.glob("*"), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
            add_p(fp, "eingang")
            if len(items) >= limit * 2: break

    items.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return items[:limit]

@bp.route("/visualizer")
@login_required
def visualizer_page():
    if _is_hx_partial_request():
        return _render_sovereign_tool(
            "visualizer",
            "Visualizer",
            "Dokumenten-Visualizer wird geladen...",
            active_tab="visualizer",
        )
    return _render_base("visualizer.html", active_tab="visualizer")

@bp.get("/api/visualizer/sources")
@login_required
def api_visualizer_sources():
    tenant = current_tenant() or "default"
    items = _collect_visualizer_items(tenant=tenant)
    return jsonify(items=items, count=len(items))

@bp.get("/api/visualizer/render")
@login_required
def api_visualizer_render():
    src_b64 = request.args.get("source", "")
    if not src_b64: return jsonify(error="missing_source"), 400
    try:
        raw_path = _unb64(src_b64)
    except Exception: return jsonify(error="invalid_source"), 400

    fp = Path(raw_path)
    if not fp.exists(): return jsonify(error="file_not_found"), 404
    if not _is_allowed_path(fp): return jsonify(error="forbidden_path"), 403
    
    if not callable(build_visualizer_payload):
        return jsonify(error="visualizer_logic_missing"), 503

    try:
        page = int(request.args.get("page", "0") or "0")
        sheet = request.args.get("sheet", "")
        force_ocr = request.args.get("force_ocr", "0") == "1"
        
        payload = build_visualizer_payload(fp, page=page, sheet=sheet, force_ocr=force_ocr)
        payload["source"] = src_b64
        payload["target_path"] = str(fp)
        return jsonify(payload)
    except Exception as e:
        logger.exception("Visualizer render failed")
        return jsonify(error="render_failed", message=str(e)), 500
