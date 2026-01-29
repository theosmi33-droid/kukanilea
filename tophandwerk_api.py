#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tophandwerk Minimal API (Option B) — v1.0
========================================

Ziel:
- UI-freier API-Server (Upload / Pending / Process / Search / Done)
- Core ist die Engine (tophandwerk_core.py)
- Später kann eine UI (Web/App) diese Endpoints nutzen.

Start:
  export PORT=5051
  export TOPHANDWERK_API_KEY="change-me"   # empfohlen
  python3 tophandwerk_api.py

Auth:
- Wenn TOPHANDWERK_API_KEY gesetzt ist:
    Header: X-API-Key: <key>
- /health ist absichtlich OHNE Key erreichbar (Monitoring/Check)
- Sonst: offen (nur für lokales Dev empfohlen!)

Endpoints:
- GET  /health
- GET  /                        (kurze API-Info; Key nötig)
- POST /upload                  (multipart/form-data file=...)
- GET  /pending                 (list)
- GET  /pending/<token>         (full pending json)
- GET  /progress/<token>        (status/progress only)
- POST /reextract/<token>       (new analysis token)
- POST /process/<token>         (JSON answers -> archive)
- GET  /done/<token>            (done json)
- GET  /search?q=...&kdnr=...   (assistant_search)
- POST /index/fullscan          (optional)
- GET  /file/<token>            (serve pending file safely)

Notes:
- Der Server läuft bewusst als Flask Dev-Server (lokal). Für Prod: gunicorn/uwsgi.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple
from functools import wraps

from flask import Flask, request, jsonify, abort, send_file

import tophandwerk_core as core


# ============================================================
# Config
# ============================================================
APP = Flask(__name__)

PORT = int(os.environ.get("PORT", "5051"))
API_KEY = (os.environ.get("TOPHANDWERK_API_KEY") or "").strip()

MAX_UPLOAD = int(os.environ.get("TOPHANDWERK_MAX_UPLOAD", str(25 * 1024 * 1024)))
APP.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD

EINGANG: Path = getattr(core, "EINGANG")
BASE_PATH: Path = getattr(core, "BASE_PATH")
PENDING_DIR: Path = getattr(core, "PENDING_DIR")
DONE_DIR: Path = getattr(core, "DONE_DIR")
SUPPORTED_EXT = getattr(
    core,
    "SUPPORTED_EXT",
    {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".txt"},
)

analyze_to_pending = getattr(core, "analyze_to_pending", None) or getattr(core, "start_background_analysis", None)
read_pending = getattr(core, "read_pending", None)
write_pending = getattr(core, "write_pending", None)
delete_pending = getattr(core, "delete_pending", None)
list_pending = getattr(core, "list_pending", None)

process_with_answers = getattr(core, "process_with_answers", None)

write_done = getattr(core, "write_done", None)
read_done = getattr(core, "read_done", None)

assistant_search = getattr(core, "assistant_search", None)
index_run_full = getattr(core, "index_run_full", None)
db_init = getattr(core, "db_init", None)


# ============================================================
# Contract guard
# ============================================================
REQUIRED = {
    "EINGANG": EINGANG,
    "BASE_PATH": BASE_PATH,
    "PENDING_DIR": PENDING_DIR,
    "DONE_DIR": DONE_DIR,
    "SUPPORTED_EXT": SUPPORTED_EXT,
    "analyze_to_pending/start_background_analysis": analyze_to_pending,
    "read_pending": read_pending,
    "write_pending": write_pending,
    "delete_pending": delete_pending,
    "list_pending": list_pending,
    "process_with_answers": process_with_answers,
    "write_done": write_done,
    "read_done": read_done,
}
_missing = [k for k, v in REQUIRED.items() if v is None]
if _missing:
    raise RuntimeError(f"Core-Contract unvollständig, fehlt: {', '.join(_missing)}")


# ============================================================
# Helpers
# ============================================================
def _now_ts() -> float:
    return time.time()


def _safe_filename(name: str) -> str:
    name = (name or "").strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    name = name.strip("._-")
    return name or "upload"


def _is_allowed_ext(filename: str) -> bool:
    try:
        return Path(filename).suffix.lower() in set(SUPPORTED_EXT)
    except Exception:
        return False


def _allowed_roots() -> List[Path]:
    return [EINGANG.resolve(), BASE_PATH.resolve(), PENDING_DIR.resolve(), DONE_DIR.resolve()]


def _is_allowed_path(fp: Path) -> bool:
    try:
        rp = fp.resolve()
        for root in _allowed_roots():
            if rp == root:
                return True
            if str(rp).startswith(str(root) + os.sep):
                return True
        return False
    except Exception:
        return False


def require_api_key(fn):
    """
    Auth middleware:
    - /health is open (monitoring)
    - if API_KEY not set => dev-open
    - else require X-API-Key
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.path == "/health":
            return fn(*args, **kwargs)

        if not API_KEY:
            return fn(*args, **kwargs)

        provided = (request.headers.get("X-API-Key") or "").strip()
        if provided != API_KEY:
            abort(401)
        return fn(*args, **kwargs)
    return wrapper


def _json_error(msg: str, code: int = 400):
    return jsonify(ok=False, error=msg), code


# ============================================================
# Routes
# ============================================================
@APP.get("/health")
@require_api_key
def health():
    return jsonify(ok=True, ts=_now_ts(), app="tophandwerk_api", max_upload=MAX_UPLOAD)


@APP.get("/")
@require_api_key
def root():
    return jsonify(
        ok=True,
        app="tophandwerk_api",
        endpoints=[
            "GET  /health",
            "GET  /",
            "POST /upload",
            "GET  /pending",
            "GET  /pending/<token>",
            "GET  /progress/<token>",
            "POST /reextract/<token>",
            "POST /process/<token>",
            "GET  /done/<token>",
            "GET  /search?q=...&kdnr=...",
            "POST /index/fullscan",
            "GET  /file/<token>",
        ],
        auth=("X-API-Key required" if API_KEY else "open (dev mode)"),
    )


@APP.post("/upload")
@require_api_key
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return _json_error("no_file", 400)

    filename = _safe_filename(f.filename)
    if not _is_allowed_ext(filename):
        return _json_error("unsupported_ext", 400)

    EINGANG.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = EINGANG / f"{ts}__{filename}"
    if dest.exists():
        dest = EINGANG / f"{ts}_{int(time.time())}__{filename}"

    try:
        f.save(dest)
    except Exception as e:
        return _json_error(f"save_failed: {e}", 500)

    try:
        token = analyze_to_pending(dest)
    except Exception as e:
        return _json_error(f"analyze_start_failed: {e}", 500)

    return jsonify(ok=True, token=token, path=str(dest), filename=filename)


@APP.get("/pending")
@require_api_key
def pending_list():
    try:
        items = list_pending() or []
        out = []
        for it in items:
            t = it.get("_token") or ""
            out.append(
                {
                    "token": t,
                    "status": it.get("status", ""),
                    "progress": float(it.get("progress", 0.0) or 0.0),
                    "progress_phase": it.get("progress_phase", ""),
                    "filename": it.get("filename", ""),
                    "path": it.get("path", ""),
                    "used_ocr": bool(it.get("used_ocr", False)),
                }
            )
        return jsonify(ok=True, items=out)
    except Exception as e:
        return _json_error(str(e), 500)


@APP.get("/pending/<token>")
@require_api_key
def pending_get(token: str):
    p = read_pending(token)
    if not p:
        return _json_error("not_found", 404)
    p2 = dict(p)
    p2["_token"] = token
    return jsonify(ok=True, pending=p2)


@APP.get("/progress/<token>")
@require_api_key
def progress_get(token: str):
    p = read_pending(token)
    if not p:
        return _json_error("not_found", 404)
    return jsonify(
        ok=True,
        token=token,
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", ""),
    )


@APP.post("/reextract/<token>")
@require_api_key
def reextract(token: str):
    p = read_pending(token)
    if not p:
        return _json_error("not_found", 404)

    src = Path(p.get("path", "") or "")
    if not src.exists():
        return _json_error("file_missing", 404)

    # pending löschen (optional)
    try:
        delete_pending(token)
    except Exception:
        pass

    try:
        new_token = analyze_to_pending(src)
    except Exception as e:
        return _json_error(f"analyze_start_failed: {e}", 500)

    return jsonify(ok=True, token=new_token, old_token=token)


@APP.post("/process/<token>")
@require_api_key
def process(token: str):
    """
    Body JSON:
      {
        "kdnr": "1234",
        "use_existing": "/path/to/existing/folder" or "",
        "name": "...",
        "addr": "...",
        "plzort": "...",
        "doctype": "RECHNUNG",
        "document_date": "2025-10-24" or ""
      }
    """
    p = read_pending(token)
    if not p:
        return _json_error("not_found", 404)

    src = Path(p.get("path", "") or "")
    if not src.exists():
        return _json_error("file_missing", 404)

    try:
        body = request.get_json(force=True, silent=False) or {}
    except Exception:
        return _json_error("invalid_json", 400)

    if not isinstance(body, dict):
        return _json_error("invalid_json_object", 400)

    answers = {
        "kdnr": body.get("kdnr", ""),
        "use_existing": body.get("use_existing", ""),
        "name": body.get("name", ""),
        "addr": body.get("addr", ""),
        "plzort": body.get("plzort", ""),
        "doctype": body.get("doctype", p.get("doctype_suggested", "SONSTIGES")),
        "document_date": body.get("document_date", ""),
    }

    try:
        folder, final_path, created_new = process_with_answers(src, answers)
    except Exception as e:
        return _json_error(f"process_failed: {e}", 500)

    done_payload = {
        "kdnr": answers["kdnr"],
        "name": answers["name"],
        "addr": answers["addr"],
        "plzort": answers["plzort"],
        "doctype": answers.get("doctype", "SONSTIGES"),
        "document_date": answers.get("document_date", ""),
        "folder": str(folder),
        "final_path": str(final_path),
        "created_new": bool(created_new),
        "objmode": ("Bestehendes Objekt" if answers.get("use_existing") else "Neues Objekt"),
    }

    try:
        write_done(token, done_payload)
    except Exception:
        # Ablage war ok, Done-Speicher optional
        pass

    try:
        delete_pending(token)
    except Exception:
        pass

    return jsonify(ok=True, token=token, done=done_payload)


@APP.get("/done/<token>")
@require_api_key
def done_get(token: str):
    d = read_done(token)
    if not d:
        return _json_error("not_found", 404)
    return jsonify(ok=True, token=token, done=d)


@APP.get("/search")
@require_api_key
def search():
    q = (request.args.get("q") or "").strip()
    kdnr = (request.args.get("kdnr") or "").strip()
    limit_raw = (request.args.get("limit") or "").strip()

    if not q:
        return _json_error("missing_q", 400)

    limit = 50
    if limit_raw:
        try:
            limit = max(1, min(200, int(limit_raw)))
        except Exception:
            limit = 50

    if assistant_search is None:
        return _json_error("assistant_search_not_available", 400)

    try:
        rows = assistant_search(query=q, kdnr=kdnr, limit=limit)
        return jsonify(ok=True, q=q, kdnr=kdnr, results=rows or [])
    except Exception as e:
        return _json_error(f"search_failed: {e}", 500)


@APP.post("/index/fullscan")
@require_api_key
def index_fullscan():
    """
    Fullscan-Index: delegiert an core.index_run_full()

    Bugfix:
    - core.index_run_full() liefert oft schon {"ok": True/False, ...}
    - jsonify(ok=True, **res) würde 'ok' doppelt übergeben -> 500
    """
    if not callable(index_run_full):
        return _json_error("not_available", 400)
    try:
        res = index_run_full() or {}
        if isinstance(res, dict):
            res.pop("ok", None)  # prevent duplicate kwarg
            return jsonify(ok=True, **res)
        # Falls core mal kein dict liefert:
        return jsonify(ok=True, result=res)
    except Exception as e:
        return _json_error(f"index_failed: {e}", 500)


@APP.get("/file/<token>")
@require_api_key
def file_pending(token: str):
    p = read_pending(token)
    if not p:
        abort(404)

    fp = Path(p.get("path", "") or "")
    if not fp.exists():
        abort(404)
    if not _is_allowed_path(fp):
        abort(403)

    return send_file(fp, as_attachment=False)


# ============================================================
# Entrypoint
# ============================================================
def _bootstrap_dirs():
    EINGANG.mkdir(parents=True, exist_ok=True)
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    _bootstrap_dirs()
    if callable(db_init):
        try:
            db_init()
        except Exception:
            pass

    print(f"Tophandwerk API listening on http://127.0.0.1:{PORT}")
    if API_KEY:
        print("Auth: X-API-Key required (except /health)")
    else:
        print("Auth: OPEN (dev mode)")
    APP.run(host="127.0.0.1", port=PORT, debug=False)
