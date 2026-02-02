#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KUKANILEA Minimal API (Option B) — v1.3 (fixed auth + dedupe + preview overview)
===============================================================================

Fixes (dein Feedback):
1) Mehrfachklick-Upload verhindert:
   - UI: Hard-Lock + Button disabled während Upload
2) Dedupe bei doppeltem Upload (auch bei 2 Nutzern):
   - Server: sha256(file bytes) => doc_id
   - Check gegen:
       a) Pending-Queue (pending JSONs mit doc_id)
       b) optional core.has_doc_id(doc_id) falls vorhanden (archiviert/indexiert)
   - Response: HTTP 409 + info
3) Preview-Fenster in Übersicht:
   - /ui zeigt Pending Liste + Preview Panel (PDF iframe / Image) + Text-Preview

Wichtig zur Unauthorized-Problematik:
- /ui ist ABSICHTLICH OHNE API-Key erreichbar (nur die UI-Seite),
  damit du sie im Browser öffnen kannst.
- Alle API-Endpunkte (upload/pending/progress/process/...) bleiben geschützt,
  wenn API_KEY gesetzt ist. Die UI sendet den Key per Header.

Start:
  export PORT=5051
  export KUKANILEA_API_KEY="change-me"        # empfohlen (Alias: TOPHANDWERK_API_KEY)
  python3 kukanilea_api.py
"""

from __future__ import annotations

import os
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple
from functools import wraps

from flask import Flask, request, jsonify, abort, send_file, render_template_string

import kukanilea_core as core


# ============================================================
# ENV helpers (KUKANILEA_* overrides TOPHANDWERK_*)
# ============================================================
def _env(key: str, default: str = "") -> str:
    k1 = f"KUKANILEA_{key}"
    k2 = f"TOPHANDWERK_{key}"
    v = os.environ.get(k1)
    if v is not None:
        return str(v)
    v = os.environ.get(k2)
    if v is not None:
        return str(v)
    return default


# ============================================================
# Config
# ============================================================
APP = Flask(__name__)
PORT = int(os.environ.get("PORT", "5051"))

# API key alias support
API_KEY = (_env("API_KEY", "") or "").strip()

MAX_UPLOAD = int(_env("MAX_UPLOAD", str(25 * 1024 * 1024)))
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

# Optional: wenn dein Core das anbietet (empfohlen)
core_has_doc_id = getattr(core, "has_doc_id", None)


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


def _sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pending_find_by_doc_id(doc_id: str) -> Optional[str]:
    """
    Returns token if a pending item already has same doc_id.
    This prevents duplicates across users uploading the same bytes.
    """
    try:
        items = list_pending() or []
        for it in items:
            if (it.get("doc_id") or "") == doc_id:
                return str(it.get("_token") or "")
    except Exception:
        pass
    return None


def require_api_key(fn):
    """
    Auth middleware:
    - /health is open (monitoring)
    - /ui is open (so browser can load UI without headers)
    - if API_KEY not set => dev-open
    - else require X-API-Key
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.path in ("/health", "/ui"):
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
# Minimal same-origin Web UI (Pending + Preview panel)
# ============================================================
UI_HTML = r"""
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KUKANILEA Systems – Upload</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
<div class="max-w-7xl mx-auto p-6 space-y-6">
  <div class="flex items-start justify-between gap-4">
    <div>
      <h1 class="text-3xl font-bold">KUKANILEA Systems</h1>
      <p class="text-slate-300 text-sm">Upload → Pending → Preview → Process → Done</p>
      <p class="text-slate-400 text-xs mt-1">Hinweis: /ui ist offen, API-Endpunkte optional per X-API-Key geschützt.</p>
    </div>
    <div class="w-96 text-right text-xs text-slate-400">
      <div>Server: <span id="server">/</span></div>
      <div>Max Upload: <span id="maxup">?</span></div>
      <div>Auth: <span id="authmode">?</span></div>
    </div>
  </div>

  <div class="grid lg:grid-cols-3 gap-6">
    <!-- Upload -->
    <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
      <div class="text-lg font-semibold">Upload</div>

      <div>
        <label class="block text-sm text-slate-300 mb-1">API Key (X-API-Key)</label>
        <input id="key" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm"
               placeholder="change-me (optional)" />
        <div class="text-xs text-slate-400 mt-1">Wird lokal im Browser gespeichert.</div>
      </div>

      <div>
        <label class="block text-sm text-slate-300 mb-1">Datei auswählen</label>
        <input id="file" type="file"
               class="block w-full text-sm
               file:mr-4 file:rounded-xl file:border-0 file:bg-slate-700 file:px-4 file:py-2
               file:text-sm file:font-semibold file:text-white hover:file:bg-slate-600" />
      </div>

      <div class="flex items-center gap-3">
        <button id="btnUpload" class="rounded-xl px-4 py-2 font-semibold bg-indigo-600 hover:bg-indigo-500">
          Hochladen
        </button>
        <button id="btnRefresh" class="rounded-xl px-4 py-2 font-semibold bg-slate-700 hover:bg-slate-600">
          Refresh
        </button>
      </div>

      <div>
        <div id="status" class="text-sm text-slate-200"></div>
        <div id="detail" class="text-xs text-slate-400 mt-1"></div>
      </div>

      <div>
        <div class="text-xs text-slate-400 mb-1" id="pLabel">0%</div>
        <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
          <div id="bar" class="h-3 w-0 bg-indigo-500"></div>
        </div>
      </div>

      <div class="text-xs text-slate-400">
        Dedupe: gleiche Datei (gleiche Bytes) wird als Duplicate geblockt (409).
      </div>
    </div>

    <!-- Pending list -->
    <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div class="flex items-center justify-between">
        <div class="text-lg font-semibold">Pending</div>
        <div class="text-xs text-slate-400">Count: <span id="pendingCount">0</span></div>
      </div>
      <div class="mt-3 space-y-2" id="pendingList"></div>
    </div>

    <!-- Preview + Process -->
    <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div class="text-lg font-semibold">Preview & Process</div>
        <div class="text-xs text-slate-400">Token: <span id="selToken">—</span></div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950/40 overflow-hidden" id="previewArea">
        <div class="p-3 text-sm text-slate-400">Wähle links ein Pending-Item.</div>
      </div>

      <div>
        <div class="text-xs text-slate-400 mb-1">Text-Preview (pending.preview)</div>
        <pre id="textPreview" class="text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-3 bg-slate-950/40 max-h-52 overflow-auto"></pre>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div class="col-span-2">
          <label class="block text-sm text-slate-300 mb-1">tenant / mandant (optional)</label>
          <input id="tenant" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="FIRMA_X" />
        </div>

        <div>
          <label class="block text-sm text-slate-300 mb-1">kdnr</label>
          <input id="kdnr" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="1234" />
        </div>
        <div>
          <label class="block text-sm text-slate-300 mb-1">document_date</label>
          <input id="docdate" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="YYYY-MM-DD" />
        </div>

        <div class="col-span-2">
          <label class="block text-sm text-slate-300 mb-1">doctype</label>
          <input id="doctype" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="RECHNUNG / ANGEBOT / ..." />
        </div>

        <div class="col-span-2">
          <label class="block text-sm text-slate-300 mb-1">name</label>
          <input id="name" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="Kunde / Objektname" />
        </div>

        <div class="col-span-2">
          <label class="block text-sm text-slate-300 mb-1">addr</label>
          <input id="addr" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="Straße 1" />
        </div>

        <div class="col-span-2">
          <label class="block text-sm text-slate-300 mb-1">plzort</label>
          <input id="plzort" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm" placeholder="12345 Ort" />
        </div>

        <div class="col-span-2">
          <label class="block text-sm text-slate-300 mb-1">use_existing (optional, Ordnerpfad)</label>
          <input id="useexisting" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 text-sm"
                 placeholder="/.../Tophandwerk_Kundenablage/..." />
        </div>

        <div class="col-span-2 flex items-center gap-3">
          <button id="btnProcess" class="rounded-xl px-4 py-2 font-semibold bg-emerald-600 hover:bg-emerald-500">
            Process
          </button>
          <button id="btnOpenFile" class="rounded-xl px-4 py-2 font-semibold bg-slate-700 hover:bg-slate-600">
            Datei öffnen
          </button>
        </div>
      </div>

      <div>
        <div class="text-xs text-slate-400 mb-1">Debug Output</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-3 bg-slate-950/40" id="out">{}</pre>
      </div>
    </div>
  </div>
</div>

<script>
(function(){
  const el = (id) => document.getElementById(id);

  const key = el("key");
  const file = el("file");
  const btnUpload = el("btnUpload");
  const btnRefresh = el("btnRefresh");

  const status = el("status");
  const detail = el("detail");
  const out = el("out");

  const bar = el("bar");
  const pLabel = el("pLabel");

  const pendingList = el("pendingList");
  const pendingCount = el("pendingCount");

  const previewArea = el("previewArea");
  const textPreview = el("textPreview");
  const selToken = el("selToken");

  const tenant = el("tenant");
  const kdnr = el("kdnr");
  const doctype = el("doctype");
  const docdate = el("docdate");
  const name = el("name");
  const addr = el("addr");
  const plzort = el("plzort");
  const useexisting = el("useexisting");

  let currentToken = "";
  let uploading = false;  // HARD LOCK gegen Mehrfachklick

  // persist key
  const saved = localStorage.getItem("kukanilea_api_key") || "";
  if(saved) key.value = saved;
  key.addEventListener("input", () => localStorage.setItem("kukanilea_api_key", (key.value||"").trim()));

  function headers(){
    const k = (key.value || "").trim();
    return k ? {"X-API-Key": k} : {};
  }

  function setProgress(p){
    const pct = Math.max(0, Math.min(100, p));
    bar.style.width = pct + "%";
    pLabel.textContent = pct.toFixed(0) + "%";
  }

  async function apiGet(url){
    const res = await fetch(url, { headers: headers(), cache:"no-store" });
    const text = await res.text();
    let j;
    try { j = JSON.parse(text); } catch(e){ j = {raw:text}; }
    return {res, j, text};
  }

  async function apiPost(url, body, isForm){
    const opts = { method: "POST", headers: headers() };
    if(isForm){
      opts.body = body;
    }else{
      opts.headers = Object.assign({}, opts.headers, {"Content-Type": "application/json"});
      opts.body = JSON.stringify(body || {});
    }
    const res = await fetch(url, opts);
    const text = await res.text();
    let j;
    try { j = JSON.parse(text); } catch(e){ j = {raw:text}; }
    return {res, j, text};
  }

  function setSelectedToken(t){
    currentToken = t || "";
    selToken.textContent = currentToken ? currentToken : "—";
  }

  function fillFromPending(p){
    const trySet = (input, val) => { if(!input.value && val) input.value = val; };

    trySet(doctype, p.doctype_suggested || "");
    trySet(docdate, p.doc_date_suggested || "");

    if(Array.isArray(p.kdnr_ranked) && p.kdnr_ranked.length && !kdnr.value){
      const top = p.kdnr_ranked[0];
      if(Array.isArray(top) && top[0]) kdnr.value = top[0];
    }
    if(Array.isArray(p.name_suggestions) && p.name_suggestions.length) trySet(name, p.name_suggestions[0]);
    if(Array.isArray(p.addr_suggestions) && p.addr_suggestions.length) trySet(addr, p.addr_suggestions[0]);
    if(Array.isArray(p.plzort_suggestions) && p.plzort_suggestions.length) trySet(plzort, p.plzort_suggestions[0]);
  }

  function renderPreview(p){
    const fn = (p.filename || "");
    const ext = (fn.split(".").pop() || "").toLowerCase();
    const url = "/file/" + encodeURIComponent(currentToken);

    if(ext === "pdf"){
      previewArea.innerHTML = `<iframe src="${url}" class="w-full" style="height:420px"></iframe>`;
    }else{
      previewArea.innerHTML = `<img src="${url}" class="w-full" />`;
    }
    textPreview.textContent = (p.preview || "").trim();
  }

  function renderPending(items){
    pendingList.innerHTML = "";
    pendingCount.textContent = String(items.length);

    if(!items.length){
      pendingList.innerHTML = `<div class="text-sm text-slate-400">Keine Pending Items.</div>`;
      return;
    }

    for(const it of items){
      const t = it.token || "";
      const st = it.status || "";
      const pr = (it.progress ?? 0);
      const ph = it.progress_phase || "";
      const fn = it.filename || "";
      const ocr = it.used_ocr ? "OCR" : "";

      const row = document.createElement("div");
      row.className = "rounded-xl border border-slate-800 bg-slate-900/40 p-3 cursor-pointer hover:bg-slate-900/70";
      row.innerHTML = `
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="text-sm font-semibold truncate">${fn}</div>
            <div class="text-xs text-slate-400 truncate">${t}</div>
          </div>
          <div class="text-right text-xs text-slate-400">
            <div>${st} ${ocr}</div>
            <div>${Math.round(pr)}% • ${ph}</div>
          </div>
        </div>
      `;

      row.addEventListener("click", async () => {
        setSelectedToken(t);
        status.textContent = "Pending laden…";
        detail.textContent = "";
        const {res, j} = await apiGet(`/pending/${encodeURIComponent(t)}`);
        out.textContent = JSON.stringify(j, null, 2);

        if(!res.ok){
          status.textContent = `Fehler: HTTP ${res.status}`;
          return;
        }
        status.textContent = "Pending geladen.";
        if(j && j.pending){
          fillFromPending(j.pending);
          renderPreview(j.pending);
        }
      });

      pendingList.appendChild(row);
    }
  }

  async function refreshPending(){
    status.textContent = "Pending wird geladen…";
    detail.textContent = "";
    const {res, j} = await apiGet("/pending");
    out.textContent = JSON.stringify(j, null, 2);

    if(!res.ok){
      status.textContent = `Fehler: HTTP ${res.status}`;
      return;
    }
    status.textContent = "Pending aktualisiert.";
    renderPending(j.items || []);
  }

  async function pollProgress(token){
    while(true){
      const {res, j} = await apiGet("/progress/" + encodeURIComponent(token));
      if(!res.ok){
        status.textContent = `Progress Fehler: HTTP ${res.status}`;
        return;
      }
      setProgress(j.progress || 0);
      detail.textContent = (j.progress_phase || "");

      if(j.status === "READY"){
        status.textContent = "Analyse fertig. Pending aktualisiert.";
        setProgress(100);
        await refreshPending();
        return;
      }
      if(j.status === "ERROR"){
        status.textContent = "Analyse-Fehler: " + (j.error || "unbekannt");
        return;
      }
      await new Promise(r => setTimeout(r, 450));
    }
  }

  // Upload (mit HARD LOCK + Button disable)
  btnUpload.addEventListener("click", async () => {
    if(uploading) return;
    const f = file.files[0];
    if(!f){
      status.textContent = "Bitte Datei auswählen.";
      return;
    }

    uploading = true;
    btnUpload.disabled = true;
    btnRefresh.disabled = true;

    status.textContent = "Upload läuft…";
    detail.textContent = "";
    out.textContent = "{}";
    setProgress(0);

    try{
      const fd = new FormData();
      fd.append("file", f);

      const {res, j} = await apiPost("/upload", fd, true);
      out.textContent = JSON.stringify(j, null, 2);

      if(res.status === 409){
        status.textContent = "Duplicate: Datei bereits vorhanden.";
        detail.textContent = (j.error || "duplicate") + (j.token ? (" • token=" + j.token) : "");
        await refreshPending();
        return;
      }

      if(!res.ok){
        status.textContent = `Upload fehlgeschlagen: HTTP ${res.status}`;
        detail.textContent = j.error || "";
        return;
      }

      if(j.token){
        status.textContent = "Upload OK. Analyse läuft…";
        setSelectedToken(j.token);
        await pollProgress(j.token);

        // auto-open pending details after ready (best effort)
        const got = await apiGet("/pending/" + encodeURIComponent(j.token));
        if(got.res.ok && got.j && got.j.pending){
          renderPreview(got.j.pending);
          fillFromPending(got.j.pending);
        }
      } else {
        status.textContent = "Upload OK, aber kein Token erhalten (unerwartet).";
      }
    } finally {
      uploading = false;
      btnUpload.disabled = false;
      btnRefresh.disabled = false;
    }
  });

  btnRefresh.addEventListener("click", refreshPending);

  el("btnOpenFile").addEventListener("click", () => {
    if(!currentToken){
      status.textContent = "Kein Token ausgewählt.";
      return;
    }
    window.open("/file/" + encodeURIComponent(currentToken), "_blank");
  });

  el("btnProcess").addEventListener("click", async () => {
    if(!currentToken){
      status.textContent = "Kein Token ausgewählt.";
      return;
    }
    const payload = {
      tenant: (tenant.value || "").trim(),
      mandant: (tenant.value || "").trim(),
      kdnr: (kdnr.value || "").trim(),
      use_existing: (useexisting.value || "").trim(),
      name: (name.value || "").trim(),
      addr: (addr.value || "").trim(),
      plzort: (plzort.value || "").trim(),
      doctype: (doctype.value || "").trim(),
      document_date: (docdate.value || "").trim()
    };

    status.textContent = "Process läuft…";
    detail.textContent = "";
    const {res, j} = await apiPost("/process/" + encodeURIComponent(currentToken), payload, false);
    out.textContent = JSON.stringify(j, null, 2);

    if(res.ok){
      status.textContent = "Process OK. Pending entfernt → Done verfügbar.";
      await refreshPending();
      // keep preview as-is
    }else{
      status.textContent = `Process fehlgeschlagen: HTTP ${res.status}`;
      detail.textContent = j.error || "";
    }
  });

  async function loadHealth(){
    const {res, j} = await apiGet("/health");
    if(res.ok){
      el("server").textContent = location.origin;
      el("maxup").textContent = (j.max_upload || "?");
      el("authmode").textContent = (j.auth || "?");
    } else {
      el("server").textContent = location.origin;
      el("authmode").textContent = "unknown";
    }
  }

  loadHealth().then(refreshPending);
})();
</script>
</body>
</html>
"""


# ============================================================
# Routes
# ============================================================
@APP.get("/health")
@require_api_key
def health():
    return jsonify(
        ok=True,
        ts=_now_ts(),
        app="kukanilea_api",
        max_upload=MAX_UPLOAD,
        auth=("X-API-Key required" if API_KEY else "open (dev mode)"),
    )


@APP.get("/")
@require_api_key
def root():
    return jsonify(
        ok=True,
        app="kukanilea_api",
        endpoints=[
            "GET  /health",
            "GET  /",
            "GET  /ui",
            "POST /upload",
            "GET  /pending",
            "GET  /pending/<token>",
            "GET  /progress/<token>",
            "POST /reextract/<token>",
            "POST /process/<token>",
            "GET  /done/<token>",
            "GET  /search?q=...&kdnr=...&limit=...",
            "POST /index/fullscan",
            "GET  /file/<token>",
        ],
        auth=("X-API-Key required (except /health,/ui)" if API_KEY else "open (dev mode)"),
    )


@APP.get("/ui")
@require_api_key
def ui():
    # /ui ist offen, damit es im Browser ohne Header lädt.
    # Die UI sendet den Key für die API Calls selbst (X-API-Key).
    return render_template_string(UI_HTML)


@APP.post("/upload")
@require_api_key
def upload():
    """
    Upload with server-side dedupe (sha256 bytes => doc_id):
      - If same doc_id exists in pending => 409 duplicate_pending + token
      - If core.has_doc_id exists and returns True => 409 duplicate_archived
    """
    f = request.files.get("file")
    if not f or not f.filename:
        return _json_error("no_file", 400)

    filename = _safe_filename(f.filename)
    if not _is_allowed_ext(filename):
        return _json_error("unsupported_ext", 400)

    EINGANG.mkdir(parents=True, exist_ok=True)

    # save first (to compute hash)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = EINGANG / f"{ts}__{filename}"
    if dest.exists():
        dest = EINGANG / f"{ts}_{int(time.time())}__{filename}"

    try:
        f.save(dest)
    except Exception as e:
        return _json_error(f"save_failed: {e}", 500)

    # compute doc_id
    try:
        doc_id = _sha256_file(dest)
    except Exception as e:
        try:
            dest.unlink()
        except Exception:
            pass
        return _json_error(f"hash_failed: {e}", 500)

    # 1) pending dedupe
    existing_token = _pending_find_by_doc_id(doc_id)
    if existing_token:
        try:
            dest.unlink()
        except Exception:
            pass
        return jsonify(ok=False, error="duplicate_pending", token=existing_token, doc_id=doc_id), 409

    # 2) archived/indexed dedupe (optional, only if core exposes it)
    if callable(core_has_doc_id):
        try:
            if bool(core_has_doc_id(doc_id)):
                try:
                    dest.unlink()
                except Exception:
                    pass
                return jsonify(ok=False, error="duplicate_archived", doc_id=doc_id), 409
        except Exception:
            # If core check fails, do not block upload (pending dedupe already helps concurrency)
            pass

    # start analysis
    try:
        token = analyze_to_pending(dest)
    except Exception as e:
        try:
            dest.unlink()
        except Exception:
            pass
        return _json_error(f"analyze_start_failed: {e}", 500)

    # write doc_id into pending payload ASAP (so dedupe works for subsequent uploads)
    try:
        p = read_pending(token) or {}
        p["doc_id"] = doc_id
        write_pending(token, p)
    except Exception:
        pass

    return jsonify(ok=True, token=token, path=str(dest), filename=filename, doc_id=doc_id)


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
                    "doc_id": it.get("doc_id", ""),
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

    # keep same file, just restart analysis with a new token
    try:
        delete_pending(token)
    except Exception:
        pass

    try:
        new_token = analyze_to_pending(src)
    except Exception as e:
        return _json_error(f"analyze_start_failed: {e}", 500)

    # preserve doc_id if available
    try:
        old_doc_id = p.get("doc_id", "")
        if old_doc_id:
            np = read_pending(new_token) or {}
            np["doc_id"] = old_doc_id
            write_pending(new_token, np)
    except Exception:
        pass

    return jsonify(ok=True, token=new_token, old_token=token)


@APP.post("/process/<token>")
@require_api_key
def process(token: str):
    """
    Body JSON:
      {
        "tenant": "FIRMA_X",              # optional (alias: "mandant")
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
        "tenant": body.get("tenant", ""),
        "mandant": body.get("mandant", ""),
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
        "tenant": answers.get("tenant") or answers.get("mandant") or p.get("tenant_suggested", ""),
        "kdnr": answers.get("kdnr", ""),
        "name": answers.get("name", ""),
        "addr": answers.get("addr", ""),
        "plzort": answers.get("plzort", ""),
        "doctype": answers.get("doctype", "SONSTIGES"),
        "document_date": answers.get("document_date", ""),
        "folder": str(folder),
        "final_path": str(final_path),
        "created_new": bool(created_new),
        "objmode": ("Bestehendes Objekt" if answers.get("use_existing") else "Neues Objekt"),
        "doc_id": p.get("doc_id", ""),
    }

    try:
        write_done(token, done_payload)
    except Exception:
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
            res.pop("ok", None)
            return jsonify(ok=True, **res)
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

    print(f"KUKANILEA API listening on http://127.0.0.1:{PORT}")
    if API_KEY:
        print("Auth: X-API-Key required (except /health and /ui)")
    else:
        print("Auth: OPEN (dev mode)")
    APP.run(host="127.0.0.1", port=PORT, debug=False)


