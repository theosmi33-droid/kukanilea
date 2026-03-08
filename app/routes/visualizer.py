from __future__ import annotations
import itertools
import logging
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request

from app.auth import login_required, current_tenant
from app.web import _unb64, _is_allowed_path, _b64
from app import core
from app.core.visualizer_markup import (
    analyze_excel_summary,
    append_markup,
    load_markup_document,
)

logger = logging.getLogger("kukanilea.visualizer")
bp = Blueprint("visualizer", __name__)

VISUALIZER_EXTS = {".pdf", ".xlsx", ".csv"}

def _core_get(name: str, default=None):
    return getattr(core, name, default)

list_pending = _core_get("list_pending")
list_recent_docs = _core_get("list_recent_docs")
build_visualizer_payload = _core_get("build_visualizer_payload")
EINGANG = _core_get("EINGANG")
BASE_PATH = _core_get("BASE_PATH")
_NOTE_COUNTER = itertools.count(1)


def _norm_tenant(value: str) -> str:
    return str(value or "default").strip().lower().replace(" ", "_")


def _is_tenant_visualizer_path(fp: Path, tenant: str) -> bool:
    """Allow visualizer access only to files in the current tenant subtree."""
    try:
        rp = fp.resolve()
    except Exception:
        return False

    tenant_key = _norm_tenant(tenant)
    scoped_roots = [root for root in (BASE_PATH, EINGANG) if isinstance(root, Path)]
    for root in scoped_roots:
        try:
            rr = root.resolve()
            rel = rp.relative_to(rr)
        except Exception:
            continue
        if not rel.parts:
            return False
        if _norm_tenant(rel.parts[0]) == tenant_key:
            return True
    return False

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

    if callable(list_pending):
        for p_info in (list_pending() or []):
            raw = p_info.get("path", "")
            if raw:
                add_p(Path(raw), "pending")

    if callable(list_recent_docs):
        try:
            for row in list_recent_docs(tenant_id=tenant, limit=limit*2) or []:
                raw = row.get("file_path") or ""
                if raw: add_p(Path(raw), "archive")
        except Exception: pass

    tenant_in = (EINGANG / tenant) if isinstance(EINGANG, Path) else None
    if tenant_in and tenant_in.exists():
        for fp in sorted(tenant_in.glob("*"), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
            add_p(fp, "eingang")
            if len(items) >= limit * 2: break

    items.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return items[:limit]

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
    if not _is_tenant_visualizer_path(fp, current_tenant() or "default"):
        return jsonify(error="forbidden_tenant_path"), 403
    
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


@bp.get("/api/visualizer/projects")
@login_required
def api_visualizer_projects():
    return jsonify(projects=[])


def _summarize_payload(payload: dict) -> str:
    kind = str(payload.get("kind") or "doc").lower()
    file_name = str((payload.get("file") or {}).get("name") or "Dokument")
    if kind == "sheet":
        rows = int((payload.get("sheet") or {}).get("rows") or 0)
        cols = int((payload.get("sheet") or {}).get("cols") or 0)
        return f"{file_name}: Tabellenansicht mit {rows} Zeilen und {cols} Spalten."
    if kind == "pdf":
        page = payload.get("page") or {}
        index = int(page.get("index") or 0) + 1
        count = max(1, int(page.get("count") or 1))
        return f"{file_name}: PDF-Seite {index} von {count} wurde erfolgreich gerendert."
    text = str((payload.get("text") or {}).get("content") or "").strip()
    if text:
        compact = " ".join(text.split())
        return f"{file_name}: {compact[:280]}" + ("…" if len(compact) > 280 else "")
    return f"{file_name}: Visualizer-Ansicht ist verfügbar."


@bp.post("/api/visualizer/summary")
@login_required
def api_visualizer_summary():
    body = request.get_json(silent=True) or {}
    src_b64 = str(body.get("source") or "")
    if not src_b64:
        return jsonify(error="missing_source"), 400
    try:
        raw_path = _unb64(src_b64)
    except Exception:
        return jsonify(error="invalid_source"), 400

    fp = Path(raw_path)
    if not fp.exists():
        return jsonify(error="file_not_found"), 404
    if not _is_allowed_path(fp):
        return jsonify(error="forbidden_path"), 403
    if not _is_tenant_visualizer_path(fp, current_tenant() or "default"):
        return jsonify(error="forbidden_tenant_path"), 403
    if not callable(build_visualizer_payload):
        return jsonify(error="visualizer_logic_missing"), 503

    page = int(body.get("page") or 0)
    sheet = str(body.get("sheet") or "")
    force_ocr = bool(body.get("force_ocr"))
    try:
        payload = build_visualizer_payload(fp, page=page, sheet=sheet, force_ocr=force_ocr)
        summary = _summarize_payload(payload if isinstance(payload, dict) else {})
    except Exception as e:
        logger.exception("Visualizer summary failed")
        return jsonify(error="summary_failed", message=str(e)), 500

    kind = str((payload or {}).get("kind") or "doc")
    excel_summary = None
    if fp.suffix.lower() in {".csv", ".xlsx"}:
        try:
            excel_summary = analyze_excel_summary(fp)
        except Exception as e:
            logger.warning("Excel analyzer failed: %s", e)

    return jsonify(
        summary=summary,
        model="heuristic",
        source={"name": fp.name, "kind": kind},
        excel_summary=excel_summary,
    )


@bp.get("/api/visualizer/markup")
@login_required
def api_visualizer_markup_get():
    project_id = str(request.args.get("project_id") or "").strip()
    if not project_id:
        return jsonify(error="missing_project_id"), 400
    tenant = current_tenant() or "default"
    base_dir = Path(current_app.instance_path)
    doc = load_markup_document(base_dir, tenant_id=tenant, project_id=project_id)
    return jsonify(ok=True, markup=doc)


@bp.post("/api/visualizer/markup")
@login_required
def api_visualizer_markup_post():
    body = request.get_json(silent=True) or {}
    project_id = str(body.get("project_id") or "").strip()
    source = str(body.get("source") or "").strip()
    if not project_id:
        return jsonify(error="missing_project_id"), 400
    if not source:
        return jsonify(error="missing_source"), 400

    tenant = current_tenant() or "default"
    base_dir = Path(current_app.instance_path)
    try:
        result = append_markup(base_dir, tenant_id=tenant, project_id=project_id, source=source, payload=body)
    except ValueError as e:
        return jsonify(error="invalid_markup", message=str(e)), 400
    except Exception as e:
        logger.exception("Failed to persist visualizer markup")
        return jsonify(error="markup_persist_failed", message=str(e)), 500
    return jsonify(ok=True, **result)


@bp.post("/api/visualizer/note")
@login_required
def api_visualizer_note():
    body = request.get_json(silent=True) or {}
    summary = str(body.get("summary") or "").strip()
    if not summary:
        return jsonify(error="missing_summary"), 400
    note_id = next(_NOTE_COUNTER)
    project_id = str(body.get("project_id") or "").strip()
    source = str(body.get("source") or "").strip()
    markup_result = None
    if project_id and source:
        tenant = current_tenant() or "default"
        base_dir = Path(current_app.instance_path)
        try:
            markup_result = append_markup(
                base_dir,
                tenant_id=tenant,
                project_id=project_id,
                source=source,
                payload={"page": body.get("page", 0), "x": body.get("x", 0), "y": body.get("y", 0), "note": summary},
            )
        except Exception:
            logger.exception("Failed to persist note as markup")

    return jsonify(ok=True, note={"id": note_id, "title": str(body.get("title") or "Visualizer Summary")}, markup=markup_result)


@bp.post("/api/visualizer/store-to-project")
@login_required
def api_visualizer_store_to_project():
    body = request.get_json(silent=True) or {}
    project_id = str(body.get("project_id") or "").strip()
    if not project_id:
        return jsonify(error="missing_project_id"), 400
    return jsonify(ok=True, task_id=f"vz-{project_id}")


@bp.post("/api/visualizer/export-pdf")
@login_required
def api_visualizer_export_pdf():
    return jsonify(error="not_implemented", message="PDF export is not configured in this runtime."), 501
