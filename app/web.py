#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KUKANILEA Systems — Upload/UI v3 (Split-View + Theme + Local Chat)
==================================================================

Drop-in Flask UI for the KUKANILEA core.

Key features:
- Queue overview (no Jinja crashes even if fields missing)
- Review Split-View: PDF/preview LEFT, wizard RIGHT
- Dark/Light mode + Accent color (stored in localStorage)
- Upload -> background analyze -> auto-open review when READY
- Re-Extract creates new token and redirects
- Optional Tasks tab (if core exposes task_* functions)
- Local Chat tab:
    - deterministic agent-orchestrator without external LLM

Run:
  source .venv/bin/activate
  PORT=5051 KUKANILEA_SECRET="change-me" python3 kukanilea_upload_v3_ui.py

Notes:
- This UI expects a local `kukanilea_core*.py` next to it.
- OCR depends on system binaries (e.g. tesseract) + python deps.
"""

from __future__ import annotations

import os
import re
import json
import time
import base64
import importlib
import importlib.util

from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template_string,
    send_file,
    abort,
    redirect,
    url_for,
    current_app,
    session,
    g,
)

from kukanilea.agents import AgentContext, CustomerAgent, SearchAgent
from kukanilea.orchestrator import Orchestrator
from .errors import json_error, error_payload
from .rate_limit import chat_limiter, search_limiter, upload_limiter
from .security import get_csrf_token
from .timeout import time_limit

from .auth import (
    current_role,
    current_tenant,
    current_user,
    hash_password,
    login_required,
    login_user,
    logout_user,
    require_role,
)
from .config import Config
from .db import AuthDB

weather_spec = importlib.util.find_spec("kukanilea_weather_plugin")
if weather_spec:
    _weather_mod = importlib.import_module("kukanilea_weather_plugin")
    get_weather = getattr(_weather_mod, "get_weather", None) or getattr(_weather_mod, "get_berlin_weather_now", None)
else:
    get_weather = None  # type: ignore

rapidfuzz_spec = importlib.util.find_spec("rapidfuzz")
if rapidfuzz_spec:
    fuzz = importlib.import_module("rapidfuzz").fuzz  # type: ignore
else:
    fuzz = None  # type: ignore

werkzeug_spec = importlib.util.find_spec("werkzeug.utils")
if werkzeug_spec:
    secure_filename = importlib.import_module("werkzeug.utils").secure_filename  # type: ignore
else:
    secure_filename = None  # type: ignore

# -------- Core import (robust) ----------
core = None
_core_import_errors = []
for mod in ("kukanilea_core_v3_fixed", "kukanilea_core_v3", "kukanilea_core"):
    try:
        core = __import__(mod)
        break
    except Exception as e:
        _core_import_errors.append(f"{mod}: {e}")

if core is None:
    raise RuntimeError("KUKANILEA core import failed: " + " | ".join(_core_import_errors))


def _core_get(name: str, default=None):
    return getattr(core, name, default)


# Paths/config from core
EINGANG: Path = _core_get("EINGANG")
BASE_PATH: Path = _core_get("BASE_PATH")
PENDING_DIR: Path = _core_get("PENDING_DIR")
DONE_DIR: Path = _core_get("DONE_DIR")
SUPPORTED_EXT = set(_core_get("SUPPORTED_EXT", {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".txt"}))

# Core functions (minimum)
analyze_to_pending = _core_get("analyze_to_pending") or _core_get("start_background_analysis")
read_pending = _core_get("read_pending")
write_pending = _core_get("write_pending")
delete_pending = _core_get("delete_pending")
list_pending = _core_get("list_pending")
write_done = _core_get("write_done")
read_done = _core_get("read_done")
process_with_answers = _core_get("process_with_answers")
normalize_component = _core_get("normalize_component", lambda s: (s or "").strip())

# Optional helpers
db_init = _core_get("db_init")
assistant_search = _core_get("assistant_search")
audit_log = _core_get("audit_log")

# Optional tasks
task_list = _core_get("task_list")
task_resolve = _core_get("task_resolve")
task_dismiss = _core_get("task_dismiss")

# Guard minimum contract
_missing = []
if EINGANG is None: _missing.append("EINGANG")
if BASE_PATH is None: _missing.append("BASE_PATH")
if PENDING_DIR is None: _missing.append("PENDING_DIR")
if DONE_DIR is None: _missing.append("DONE_DIR")
if not callable(analyze_to_pending): _missing.append("analyze_to_pending")
for fn in (read_pending, write_pending, delete_pending, list_pending, write_done, read_done, process_with_answers):
    if fn is None:
        _missing.append("core_fn_missing")
        break
if _missing:
    raise RuntimeError("Core contract incomplete: " + ", ".join(_missing))


# -------- Flask ----------
bp = Blueprint("web", __name__)
ORCHESTRATOR = None

# --- Early template defaults (avoid NameError during debug reload) ---
HTML_LOGIN = ""  # will be overwritten later by the full template block


def suggest_existing_folder(base_path: str, tenant: str, kdnr: str, name: str) -> Tuple[str, float]:
    """Heuristic: find an existing customer folder for this tenant."""
    try:
        root = Path(base_path) / tenant
        if not root.exists():
            return "", 0.0
        k = (kdnr or "").strip()
        n = (name or "").strip().lower()
        candidates = []
        for p in root.glob("*"):
            if not p.is_dir():
                continue
            s = p.name.lower()
            if k and s.startswith(k.lower() + "_"):
                return str(p), 0.95
            if n and n in s:
                candidates.append((str(p), 0.7))
            if n and fuzz is not None:
                score = fuzz.partial_ratio(n, s) / 100.0
                if score >= 0.6:
                    candidates.append((str(p), score))
        if not candidates:
            return "", 0.0
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]
    except Exception:
        return "", 0.0

DOCTYPE_CHOICES = [
    "ANGEBOT", "RECHNUNG", "AUFTRAGSBESTAETIGUNG", "AW",
    "MAHNUNG", "NACHTRAG", "SONSTIGES", "FOTO",
    "H_RECHNUNG", "H_ANGEBOT",
]

ASSISTANT_HIDE_EINGANG = True


# -------- Helpers ----------
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode((s or "").encode("utf-8")).decode("ascii")


def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode((s or "").encode("ascii")).decode("utf-8", errors="ignore")


def _audit(action: str, target: str = "", meta: dict = None) -> None:
    if audit_log is None:
        return
    try:
        role = current_role()
        user = current_user() or ""
        audit_log(user=user, role=role, action=action, target=target, meta=meta or {}, tenant_id=current_tenant())
    except Exception:
        pass


def _allowlisted_dirs() -> List[Path]:
    base = Config.BASE_DIR
    instance_dir = base / "instance"
    core_db_dir = Path(getattr(core, "DB_PATH", instance_dir)).resolve().parent
    return [instance_dir.resolve(), core_db_dir]


def _is_allowlisted_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False
    for allowed in _allowlisted_dirs():
        try:
            if resolved.is_relative_to(allowed):
                return True
        except AttributeError:
            if str(resolved).startswith(str(allowed)):
                return True
    return False


def _list_allowlisted_db_files() -> List[Path]:
    files: List[Path] = []
    for folder in _allowlisted_dirs():
        if not folder.exists():
            continue
        for fp in folder.glob("*.db"):
            files.append(fp)
        for fp in folder.glob("*.sqlite3"):
            files.append(fp)
    return sorted({f.resolve() for f in files})


def _list_allowlisted_base_paths() -> List[Path]:
    candidates = {BASE_PATH.resolve()}
    base_dir = Config.BASE_DIR.resolve()
    data_dir = base_dir / "data"
    if data_dir.exists():
        candidates.add(data_dir.resolve())
    return sorted(candidates)


def _is_storage_path_valid(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        return False
    return resolved.exists() and resolved.is_dir()


def _seed_dev_users(auth_db: AuthDB) -> str:
    now = datetime.utcnow().isoformat()
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_tenant("KUKANILEA Dev", "KUKANILEA Dev", now)
    auth_db.upsert_user("admin", hash_password("admin"), now)
    auth_db.upsert_user("dev", hash_password("dev"), now)
    auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    auth_db.upsert_membership("dev", "KUKANILEA Dev", "DEV", now)
    return "Seeded users: admin/admin, dev/dev"


def _rate_key() -> str:
    user = current_user() or "anon"
    ip = request.remote_addr or "unknown"
    return f"{user}:{ip}"


def _safe_filename(name: str) -> str:
    raw = (name or "").strip().replace("\\", "_").replace("/", "_")
    if secure_filename is not None:
        out = secure_filename(raw)
        return out or "upload"
    raw = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._-")
    return raw or "upload"


def _is_allowed_ext(filename: str) -> bool:
    try:
        return Path(filename).suffix.lower() in SUPPORTED_EXT
    except Exception:
        return False


def _allowed_roots() -> List[Path]:
    return [EINGANG.resolve(), BASE_PATH.resolve(), PENDING_DIR.resolve(), DONE_DIR.resolve()]


def _is_allowed_path(fp: Path) -> bool:
    try:
        rp = fp.resolve()
        for root in _allowed_roots():
            if rp == root or str(rp).startswith(str(root) + os.sep):
                return True
        return False
    except Exception:
        return False


def _norm_tenant(t: str) -> str:
    t = normalize_component(t or "").lower().replace(" ", "_")
    t = re.sub(r"[^a-z0-9_\-]+", "", t)
    return t[:40]


def _wizard_get(p: dict) -> dict:
    w = p.get("wizard") or {}
    w.setdefault("tenant", "")
    w.setdefault("kdnr", "")
    w.setdefault("use_existing", "")
    w.setdefault("name", "")
    w.setdefault("addr", "")
    w.setdefault("plzort", "")
    w.setdefault("doctype", "")
    w.setdefault("document_date", "")
    return w


def _wizard_save(token: str, p: dict, w: dict) -> None:
    p["wizard"] = w
    write_pending(token, p)


def _card(kind: str, msg: str) -> str:
    styles = {
        "error": "border-red-500/40 bg-red-500/10",
        "warn": "border-amber-500/40 bg-amber-500/10",
        "info": "border-slate-700 bg-slate-950/40",
    }
    s = styles.get(kind, styles["info"])
    return f'<div class="rounded-xl border {s} p-3 text-sm">{msg}</div>'


def _render_base(content: str, active_tab: str = "upload") -> str:
    profile = _get_profile()
    return render_template_string(
        HTML_BASE,
        content=content,
        ablage=str(BASE_PATH),
        user=current_user() or "-",
        roles=current_role(),
        tenant=current_tenant() or "-",
        profile=profile,
        csrf_token=get_csrf_token(),
        active_tab=active_tab
    )


def _get_profile() -> dict:
    if callable(getattr(core, "get_profile", None)):
        return core.get_profile()
    return {"name": "default", "db_path": str(getattr(core, "DB_PATH", "")), "base_path": str(BASE_PATH)}


# -------- UI Templates ----------
HTML_BASE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="csrf-token" content="{{ csrf_token }}">
<title>KUKANILEA Systems</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  const savedTheme = localStorage.getItem("ks_theme") || "dark";
  const savedAccent = localStorage.getItem("ks_accent") || "indigo";
  if(savedTheme === "light"){ document.documentElement.classList.add("light"); }
  document.documentElement.dataset.accent = savedAccent;
  window.KS_CSRF = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  window.KS_SAFE_MODE = localStorage.getItem("ks_safe_mode") === "1";
</script>
<style>
  :root{
    --bg:#0b1220;
    --bg-elev:#111a2c;
    --bg-panel:#0f172a;
    --border:rgba(148,163,184,.15);
    --text:#e2e8f0;
    --muted:#94a3b8;
    --accent-500:#6366f1;
    --accent-600:#4f46e5;
    --shadow:0 8px 30px rgba(15,23,42,.35);
    --radius-lg:18px;
    --radius-md:14px;
  }
  html[data-accent="indigo"]{ --accent-500:#6366f1; --accent-600:#4f46e5; }
  html[data-accent="emerald"]{ --accent-500:#10b981; --accent-600:#059669; }
  html[data-accent="amber"]{ --accent-500:#f59e0b; --accent-600:#d97706; }
  .light body{
    --bg:#f8fafc;
    --bg-elev:#ffffff;
    --bg-panel:#ffffff;
    --border:rgba(148,163,184,.25);
    --text:#0f172a;
    --muted:#475569;
    --shadow:0 8px 30px rgba(15,23,42,.12);
  }
  body{ background:var(--bg); color:var(--text); }
  .app-shell{ display:flex; min-height:100vh; }
  .app-nav{
    width:240px; background:var(--bg-elev); border-right:1px solid var(--border);
    padding:24px 18px; position:sticky; top:0; height:100vh;
  }
  .app-main{ flex:1; display:flex; flex-direction:column; }
  .app-topbar{
    display:flex; justify-content:space-between; align-items:center;
    padding:22px 28px; border-bottom:1px solid var(--border); background:var(--bg-elev);
  }
  .app-content{ padding:24px 28px; }
  .nav-link{
    display:flex; gap:12px; align-items:center; padding:10px 12px; border-radius:12px;
    color:var(--muted); text-decoration:none; transition:all .15s ease;
  }
  .nav-link:hover{ background:rgba(148,163,184,.08); color:var(--text); }
  .nav-link.active{ background:rgba(99,102,241,.15); color:var(--text); border:1px solid rgba(99,102,241,.25); }
  .badge{ font-size:11px; padding:3px 8px; border-radius:999px; border:1px solid var(--border); color:var(--muted); }
  .card{ background:var(--bg-panel); border:1px solid var(--border); border-radius:var(--radius-lg); box-shadow:var(--shadow); }
  .btn-primary{ background:var(--accent-600); color:white; border-radius:12px; }
  .btn-outline{ border:1px solid var(--border); border-radius:12px; }
  .input{ background:transparent; border:1px solid var(--border); border-radius:12px; }
  .muted{ color:var(--muted); }
  .pill{ background:rgba(99,102,241,.12); color:var(--text); border:1px solid rgba(99,102,241,.2); padding:2px 8px; border-radius:999px; font-size:11px; }
</style>
</head>
<body>
<div class="app-shell">
  <aside class="app-nav">
    <div class="flex items-center gap-2 mb-6">
      <div class="h-10 w-10 rounded-2xl flex items-center justify-center" style="background:rgba(99,102,241,.2);">✦</div>
      <div>
        <div class="text-sm font-semibold">KUKANILEA</div>
        <div class="text-[11px] muted">Agent Orchestra</div>
      </div>
    </div>
    <nav class="space-y-2">
      <a class="nav-link {{'active' if active_tab=='upload' else ''}}" href="/">📥 Upload</a>
      <a class="nav-link {{'active' if active_tab=='tasks' else ''}}" href="/tasks">✅ Tasks</a>
      <a class="nav-link {{'active' if active_tab=='assistant' else ''}}" href="/assistant">🧠 Assistant</a>
      <a class="nav-link {{'active' if active_tab=='chat' else ''}}" href="/chat">💬 Chat</a>
      <a class="nav-link {{'active' if active_tab=='time' else ''}}" href="/time">⏱️ Time</a>
      <a class="nav-link {{'active' if active_tab=='mail' else ''}}" href="/mail">✉️ Mail</a>
      {% if roles == 'DEV' %}
      <a class="nav-link {{'active' if active_tab=='settings' else ''}}" href="/settings">🛠️ Settings</a>
      {% endif %}
    </nav>
    <div class="mt-8 text-xs muted">
      Ablage: {{ablage}}
    </div>
  </aside>
  <main class="app-main">
    <div class="app-topbar">
      <div>
        <div class="text-lg font-semibold">Workspace</div>
        <div class="text-xs muted">Upload → Review → Ablage</div>
      </div>
      <div class="flex items-center gap-3">
        <span class="badge">User: {{user}}</span>
        <span class="badge">Role: {{roles}}</span>
        <span class="badge">Tenant: {{tenant}}</span>
        <span class="badge">Profile: {{ profile.name }}</span>
        {% if user and user != '-' %}
        <a class="px-3 py-2 text-sm btn-outline" href="/logout">Logout</a>
        {% endif %}
        <button id="accentBtn" class="px-3 py-2 text-sm btn-outline">Accent: <span id="accentLabel"></span></button>
        <button id="themeBtn" class="px-3 py-2 text-sm btn-outline">Theme: <span id="themeLabel"></span></button>
      </div>
    </div>
    <div class="app-content">
      {{ content|safe }}
    </div>
  </main>
</div>

<!-- Floating Chat Widget -->
<div id="chatWidgetBtn" title="Chat" class="fixed bottom-6 right-6 z-50 cursor-pointer select-none">
  <div class="relative h-12 w-12 rounded-full flex items-center justify-center" style="background:var(--accent-600); box-shadow:var(--shadow); color:white;">
    💬
    <span id="chatUnread" class="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-rose-500 hidden"></span>
  </div>
</div>

<div id="chatDrawer" class="fixed inset-y-0 right-0 z-50 hidden w-[420px] max-w-[92vw] border-l" style="background:var(--bg-elev); border-color:var(--border); box-shadow:var(--shadow);">
  <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--border);">
    <div>
      <div class="text-sm font-semibold">KUKANILEA Assistant</div>
      <div class="text-xs muted">Tenant: {{tenant}}</div>
    </div>
    <div class="flex items-center gap-2">
      <span id="chatWidgetStatus" class="text-[11px] muted">Bereit</span>
      <button id="chatWidgetClose" class="rounded-lg px-2 py-1 text-sm btn-outline">✕</button>
    </div>
  </div>
  <div class="px-4 py-3 border-b" style="border-color:var(--border);">
    <div class="flex flex-wrap gap-2">
      <button class="chat-quick pill" data-q="suche rechnung">Suche Rechnung</button>
      <button class="chat-quick pill" data-q="suche angebot">Suche Angebot</button>
      <button class="chat-quick pill" data-q="zeige letzte uploads">Letzte Uploads</button>
      <button class="chat-quick pill" data-q="hilfe">Hilfe</button>
    </div>
  </div>
  <div id="chatWidgetMsgs" class="flex-1 overflow-auto px-4 py-4 space-y-3 text-sm" style="height: calc(100vh - 230px);"></div>
  <div class="border-t px-4 py-3 space-y-2" style="border-color:var(--border);">
    <div class="flex gap-2">
      <input id="chatWidgetKdnr" class="w-24 rounded-xl input px-3 py-2 text-sm" placeholder="KDNR" />
      <input id="chatWidgetInput" class="flex-1 rounded-xl input px-3 py-2 text-sm" placeholder="Frag etwas…" />
      <button id="chatWidgetSend" class="rounded-xl px-3 py-2 text-sm btn-primary">Senden</button>
    </div>
    <div class="flex items-center justify-between">
      <button id="chatWidgetRetry" class="text-xs btn-outline px-3 py-1 hidden">Retry</button>
      <button id="chatWidgetClear" class="text-xs btn-outline px-3 py-1">Clear</button>
    </div>
  </div>
</div>

<script>
(function(){
  const btnTheme = document.getElementById("themeBtn");
  const lblTheme = document.getElementById("themeLabel");
  const btnAcc = document.getElementById("accentBtn");
  const lblAcc = document.getElementById("accentLabel");
  function curTheme(){ return (localStorage.getItem("ks_theme") || "dark"); }
  function curAccent(){ return (localStorage.getItem("ks_accent") || "indigo"); }
  function applyTheme(t){
    if(t === "light"){ document.documentElement.classList.add("light"); }
    else { document.documentElement.classList.remove("light"); }
    localStorage.setItem("ks_theme", t);
    lblTheme.textContent = t;
  }
  function applyAccent(a){
    document.documentElement.dataset.accent = a;
    localStorage.setItem("ks_accent", a);
    lblAcc.textContent = a;
  }
  applyTheme(curTheme());
  applyAccent(curAccent());
  btnTheme?.addEventListener("click", ()=>{ applyTheme(curTheme() === "dark" ? "light" : "dark"); });
  btnAcc?.addEventListener("click", ()=>{
    const order = ["indigo","emerald","amber"];
    const i = order.indexOf(curAccent());
    applyAccent(order[(i+1) % order.length]);
  });
})();
</script>

</body>
</html>"""

# ------------------------------
# Login template
# ------------------------------
HTML_LOGIN = r"""
<div class="max-w-md mx-auto mt-10">
  <div class="card p-6">
    <h1 class="text-2xl font-bold mb-2">Login</h1>
    <p class="text-sm opacity-80 mb-4">Accounts: <b>admin</b>/<b>admin</b> (Tenant: KUKANILEA) • <b>dev</b>/<b>dev</b> (Tenant: KUKANILEA Dev)</p>
    {% if error %}<div class="alert alert-error mb-3">{{ error }}</div>{% endif %}
    <form method="post" class="space-y-3">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <div>
        <label class="label">Username</label>
        <input class="input w-full" name="username" autocomplete="username" required>
      </div>
      <div>
        <label class="label">Password</label>
        <input class="input w-full" type="password" name="password" autocomplete="current-password" required>
      </div>
      <button class="btn btn-primary w-full" type="submit">Login</button>
    </form>
  </div>
</div>
"""


HTML_INDEX = r"""<div class="grid lg:grid-cols-2 gap-6">
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Datei hochladen</div>
    <div class="muted text-sm mb-4">Upload → Analyse → Review öffnet automatisch.</div>
    <form id="upform" class="space-y-3">
      <input id="file" name="file" type="file"
        class="block w-full text-sm input
        file:mr-4 file:rounded-xl file:border-0 file:bg-slate-700 file:px-4 file:py-2
        file:text-sm file:font-semibold file:text-white hover:file:bg-slate-600" />
      <button id="btn" type="submit" class="rounded-xl px-4 py-2 font-semibold btn-primary">Hochladen</button>
    </form>
    <div class="mt-4">
      <div class="text-xs muted mb-1" id="pLabel">0.0%</div>
      <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden"><div id="bar" class="h-3 w-0" style="background:var(--accent-500)"></div></div>
      <div class="text-slate-300 text-sm mt-3" id="status"></div>
      <div class="muted text-xs mt-1" id="phase"></div>
    </div>
  </div>
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Review Queue</div>
    {% if items %}
      <div class="space-y-2">
        {% for it in items %}
          <div class="rounded-xl border border-slate-800 hover:border-slate-600 px-3 py-2">
            <div class="flex items-center justify-between gap-2">
              <a class="text-sm font-semibold underline accentText" href="/review/{{it}}/kdnr">Review öffnen</a>
              <div class="muted text-xs">{{ (meta.get(it, {}).get('progress', 0.0) or 0.0) | round(1) }}%</div>
            </div>
            <div class="muted text-xs break-all">{{ meta.get(it, {}).get('filename','') }}</div>
            <div class="muted text-[11px]">{{ meta.get(it, {}).get('progress_phase','') }}</div>
            <div class="mt-2 flex gap-2">
              <a class="rounded-xl px-3 py-2 text-xs btn-outline card" href="/file/{{it}}" target="_blank">Datei</a>
              <form method="post" action="/review/{{it}}/delete" onsubmit="return confirm('Pending wirklich löschen?')" style="display:inline;">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <button class="rounded-xl px-3 py-2 text-xs btn-outline card" type="submit">Delete</button>
              </form>
            </div>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <div class="muted text-sm">Keine offenen Reviews.</div>
    {% endif %}
  </div>
</div>
<script>
const form = document.getElementById("upform");
const fileInput = document.getElementById("file");
const bar = document.getElementById("bar");
const pLabel = document.getElementById("pLabel");
const status = document.getElementById("status");
const phase = document.getElementById("phase");
function setProgress(p){
  const pct = Math.max(0, Math.min(100, p));
  bar.style.width = pct + "%";
  pLabel.textContent = pct.toFixed(1) + "%";
}
async function poll(token){
  const res = await fetch("/api/progress/" + token, {cache:"no-store", credentials:"same-origin", headers: {"X-CSRF-Token": window.KS_CSRF}});
  const j = await res.json();
  setProgress(j.progress || 0);
  phase.textContent = j.progress_phase || "";
  if(j.status === "READY"){ status.textContent = "Analyse fertig. Review öffnet…"; setTimeout(()=>{ window.location.href = "/review/" + token + "/kdnr"; }, 120); return; }
  if(j.status === "ERROR"){ status.textContent = "Analyse-Fehler: " + (j.error || "unbekannt"); return; }
  setTimeout(()=>poll(token), 450);
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = fileInput.files[0];
  if(!f){ status.textContent = "Bitte eine Datei auswählen."; return; }
  const fd = new FormData();
  fd.append("file", f);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);
  xhr.setRequestHeader("X-CSRF-Token", window.KS_CSRF);
  xhr.upload.onprogress = (ev) => {
    if(ev.lengthComputable){ setProgress((ev.loaded / ev.total) * 35); phase.textContent = "Upload…"; }
  };
  xhr.onload = () => {
    if(xhr.status === 200){
      const resp = JSON.parse(xhr.responseText);
      status.textContent = "Upload OK. Analyse läuft…";
      poll(resp.token);
    } else {
      try{
        const j = JSON.parse(xhr.responseText || "{}");
        status.textContent = "Fehler beim Upload: " + (j.error?.message || j.error || ("HTTP " + xhr.status));
      }
      catch(e){ status.textContent = "Fehler beim Upload: HTTP " + xhr.status; }
    }
  };
  xhr.onerror = () => { status.textContent = "Upload fehlgeschlagen (Netzwerk/Server)."; };
  status.textContent = "Upload läuft…"; setProgress(0); phase.textContent = ""; xhr.send(fd);
});
</script>"""

HTML_REVIEW_SPLIT = r"""<div class="grid lg:grid-cols-2 gap-4">
  <div class="card p-4 sticky top-6 h-fit">
    <div class="flex items-center justify-between gap-2">
      <div>
        <div class="text-lg font-semibold">Dokument</div>
        <div class="muted text-xs break-all">{{filename}}</div>
      </div>
      <div class="flex items-center gap-2 text-xs">
        <a class="underline" href="/file/{{token}}" target="_blank">Download</a>
        <a class="underline muted" href="/">Home</a>
      </div>
    </div>
    <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
      <div class="badge">KDNR: {{w.kdnr or '-'}}</div>
      <div class="badge">Typ: {{suggested_doctype}}</div>
      <div class="badge">Datum: {{suggested_date or '-'}}</div>
      <div class="badge">Confidence: {{confidence}}%</div>
    </div>
    <div class="mt-3 rounded-xl overflow-hidden border" style="border-color:var(--border); height:70vh;">
      {% if is_pdf %}
        <iframe src="/file/{{token}}#page=1" class="w-full h-full"></iframe>
      {% elif is_text %}
        <iframe src="/file/{{token}}" class="w-full h-full"></iframe>
      {% else %}
        <img src="/file/{{token}}" class="w-full h-full object-contain"/>
      {% endif %}
    </div>
    {% if preview %}
      <div class="mt-3">
        <div class="text-sm font-semibold mb-1">Preview (Auszug)</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border p-3 max-h-48 overflow-auto" style="border-color:var(--border); background:rgba(15,23,42,.35);">{{preview}}</pre>
      </div>
    {% endif %}
  </div>
  <div class="card p-4">
    {{ right|safe }}
  </div>
</div>"""

HTML_WIZARD = r"""<form method="post" class="space-y-3" autocomplete="off">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
  <div class="flex items-start justify-between gap-3">
    <div>
      <div class="text-lg font-semibold">Review</div>
      <div class="muted text-xs">Bearbeitung rechts, Preview links.</div>
    </div>
    <div class="flex gap-2">
      <button class="rounded-xl px-3 py-2 text-xs btn-outline card" name="reextract" value="1" type="submit">Re-Extract</button>
    </div>
  </div>
  {% if msg %}
    <div class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">{{msg}}</div>
  {% endif %}
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">Kundennr (KDNR)</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="kdnr" value="{{w.kdnr}}" placeholder="z.B. 1234"/>
    </div>
  </div>
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">Dokumenttyp</label>
      <select class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="doctype">
        {% for d in doctypes %}
          <option value="{{d}}" {{'selected' if d==w.doctype else ''}}>{{d}}</option>
        {% endfor %}
      </select>
      <div class="muted text-[11px] mt-1">Vorschlag: {{suggested_doctype}}</div>
    </div>
    <div>
      <label class="muted text-xs">Dokumentdatum (optional)</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="document_date" value="{{w.document_date}}" placeholder="YYYY-MM-DD oder leer"/>
      <div class="muted text-[11px] mt-1">Vorschlag: {{suggested_date or '-'}} </div>
    </div>
  </div>
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">Name</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="name" value="{{w.name}}" placeholder="z.B. Gerd Warmbrunn"/>
    </div>
    <div>
      <label class="muted text-xs">Adresse</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="addr" value="{{w.addr}}" placeholder="Straße + Nr"/>
    </div>
  </div>
  <div class="grid md:grid-cols-2 gap-3">
    <div>
      <label class="muted text-xs">PLZ Ort</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="plzort" value="{{w.plzort}}" placeholder="z.B. 16341 Panketal"/>
    </div>
    <div>
      <label class="muted text-xs">Existing Folder (optional)</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="use_existing" value="{{w.use_existing}}" placeholder="Pfad eines existierenden Objektordners"/>
      {% if existing_folder_hint %}
        <div class="muted text-[11px] mt-1">Meintest du: {{existing_folder_hint}} (Confidence {{existing_folder_score}})</div>
      {% endif %}
    </div>
  </div>
  <div class="pt-2 flex flex-wrap gap-2">
    <button class="rounded-xl px-4 py-2 font-semibold btn-primary" name="confirm" value="1" type="submit">Alles korrekt → Ablage</button>
    <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/">Zurück</a>
  </div>
  <div class="mt-3">
    <div class="text-sm font-semibold">Extrahierter Text</div>
    <div class="muted text-xs">Read-only. Re-Extract aktualisiert Vorschläge.</div>
    <textarea class="w-full text-xs rounded-xl border border-slate-800 p-3 bg-slate-950/40 input mt-2" style="height:260px" readonly>{{extracted_text}}</textarea>
  </div>
</form>"""

HTML_CHAT = r"""<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
  <div class="flex items-center justify-between gap-2">
    <div>
      <div class="text-lg font-semibold">Local Chat</div>
      <div class="muted text-sm">Tool-fähiger Chat mit Agent-Orchestrator (lokal, deterministisch).</div>
    </div>
  </div>
  <div class="mt-4 flex flex-col md:flex-row gap-2">
    <input id="kdnr" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input md:w-48" placeholder="Kdnr optional" />
    <input id="q" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input flex-1" placeholder="Frag etwas… z.B. 'suche Rechnung KDNR 12393'" />
    <button id="send" class="rounded-xl px-4 py-2 font-semibold btn-primary md:w-40">Senden</button>
  </div>
  <div class="mt-2 flex items-center gap-3 text-xs muted">
    <label class="inline-flex items-center gap-2">
      <input id="safeMode" type="checkbox" class="rounded border border-slate-700 bg-slate-800" />
      Safe Mode (LLM aus)
    </label>
    <span id="chatStatus"></span>
  </div>
  <div class="mt-4 rounded-xl border border-slate-800 bg-slate-950/40 p-3" style="height:62vh; overflow:auto" id="log"></div>
  <div class="muted text-xs mt-3">
    Tipp: Nutze „öffne &lt;token&gt;“ um direkt in die Review-Ansicht zu springen.
  </div>
</div>
<script>
(function(){
  const log = document.getElementById("log");
  const q = document.getElementById("q");
  const kdnr = document.getElementById("kdnr");
  const send = document.getElementById("send");
  const safeMode = document.getElementById("safeMode");
  const chatStatus = document.getElementById("chatStatus");
  if(safeMode){
    safeMode.checked = window.KS_SAFE_MODE === true;
    safeMode.addEventListener("change", () => {
      window.KS_SAFE_MODE = safeMode.checked;
      localStorage.setItem("ks_safe_mode", safeMode.checked ? "1" : "0");
    });
  }
  function setStatus(msg){ if(chatStatus) chatStatus.textContent = msg; }
  async function postWithRetry(url, body, attempts=2){
    let lastErr = null;
    for(let i=0; i<=attempts; i++){
      try{
        const res = await fetch(url, {
          method:"POST",
          credentials:"same-origin",
          headers: {"Content-Type":"application/json", "X-CSRF-Token": window.KS_CSRF},
          body: JSON.stringify(body)
        });
        let j = {};
        try{ j = await res.json(); }catch(e){}
        if(!res.ok){
          const msg = j.error?.message || j.message || j.error || ("HTTP " + res.status);
          throw new Error(msg);
        }
        return j;
      }catch(e){
        lastErr = e;
        await new Promise(r => setTimeout(r, 300 * (i + 1)));
      }
    }
    throw lastErr || new Error("Unbekannter Fehler");
  }
  async function createTaskFromChat(text){
    if(!text) return;
    try{
      await postWithRetry("/api/tasks", {title: "Chat Follow-up", details: text});
      setStatus("Task erstellt.");
    }catch(e){
      setStatus("Task Fehler: " + (e && e.message ? e.message : e));
    }
  }
  function add(role, text, actions, results, suggestions, debug){
    const d = document.createElement("div");
    d.className = "mb-3";
    const label = document.createElement("div");
    label.className = "muted text-[11px]";
    label.textContent = role;
    const body = document.createElement("div");
    body.className = "text-sm whitespace-pre-wrap";
    body.textContent = text;
    d.appendChild(label);
    d.appendChild(body);

    const pillWrap = document.createElement("div");
    pillWrap.className = "mt-2 flex flex-wrap gap-2";
    if(actions && actions.length){
      actions.forEach((a) => {
        if(a.type === "open_token" && a.token){
          const link = document.createElement("a");
          link.href = "/review/" + a.token;
          link.textContent = "Öffnen " + a.token.slice(0,10) + "…";
          link.className = "inline-block rounded-full border px-2 py-1 text-xs hover:bg-slate-800";
          pillWrap.appendChild(link);
        } else if(a.type){
          const tag = document.createElement("span");
          tag.className = "inline-block rounded-full border px-2 py-1 text-xs";
          tag.textContent = "Action: " + a.type;
          pillWrap.appendChild(tag);
        }
      });
    }
    if(results && results.length){
      results.forEach((r) => {
        const token = r.doc_id || "";
        const label = r.file_name || token || "Dokument";
        if(token){
          const link = document.createElement("a");
          link.href = "/review/" + token;
          link.textContent = label;
          link.className = "inline-block rounded-full border px-2 py-1 text-xs hover:bg-slate-800";
          pillWrap.appendChild(link);
        }
      });
    }
    if(suggestions && suggestions.length){
      suggestions.forEach((s) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "inline-block rounded-full border px-2 py-1 text-xs hover:bg-slate-800 chat-suggestion";
        btn.dataset.q = s;
        btn.textContent = s;
        pillWrap.appendChild(btn);
      });
    }
    if(pillWrap.childElementCount){
      d.appendChild(pillWrap);
    }

    if(role === "assistant"){
      const actionRow = document.createElement("div");
      actionRow.className = "mt-2 flex gap-2";
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "rounded-full border px-2 py-1 text-xs hover:bg-slate-800";
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", async () => {
        try{ await navigator.clipboard.writeText(text || ""); }catch(e){}
      });
      const taskBtn = document.createElement("button");
      taskBtn.type = "button";
      taskBtn.className = "rounded-full border px-2 py-1 text-xs hover:bg-slate-800";
      taskBtn.textContent = "Create Task";
      taskBtn.addEventListener("click", async () => {
        await createTaskFromChat(text);
      });
      actionRow.appendChild(copyBtn);
      actionRow.appendChild(taskBtn);
      d.appendChild(actionRow);
      if(debug){
        const details = document.createElement("details");
        details.className = "mt-2 text-xs";
        const summary = document.createElement("summary");
        summary.textContent = "Explain why (DEV)";
        const pre = document.createElement("pre");
        pre.className = "mt-1 rounded-lg border border-slate-800 p-2 bg-slate-950/40 whitespace-pre-wrap";
        pre.textContent = JSON.stringify(debug, null, 2);
        details.appendChild(summary);
        details.appendChild(pre);
        d.appendChild(details);
      }
    }

    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  async function doSend(){
    const msg = (q.value || "").trim();
    if(!msg) return;
    add("you", msg);
    q.value = "";
    send.disabled = true;
    setStatus("Sende…");
    try{
      const j = await postWithRetry("/api/chat", {q: msg, kdnr: (kdnr.value||"").trim(), safe_mode: window.KS_SAFE_MODE || false});
      add("assistant", j.message || "(leer)", j.actions || [], j.results || [], j.suggestions || [], j.debug || null);
      setStatus(j.ok === false ? "Hinweis" : "OK");
    }catch(e){ add("system", "Netzwerkfehler: " + (e && e.message ? e.message : e)); }
    finally{ send.disabled = false; }
  }
  send.addEventListener("click", doSend);
  q.addEventListener("keydown", (e)=>{ if(e.key==="Enter"){ e.preventDefault(); doSend(); }});
  log.addEventListener("click", (e) => {
    const btn = e.target.closest(".chat-suggestion");
    if(!btn) return;
    q.value = btn.dataset.q || "";
    doSend();
  });

  // ---- Floating Chat Widget ----
  const _cw = {
    btn: document.getElementById('chatWidgetBtn'),
    drawer: document.getElementById('chatDrawer'),
    close: document.getElementById('chatWidgetClose'),
    msgs: document.getElementById('chatWidgetMsgs'),
    input: document.getElementById('chatWidgetInput'),
    send: document.getElementById('chatWidgetSend'),
    kdnr: document.getElementById('chatWidgetKdnr'),
    clear: document.getElementById('chatWidgetClear'),
    status: document.getElementById('chatWidgetStatus'),
    retry: document.getElementById('chatWidgetRetry'),
    unread: document.getElementById('chatUnread'),
    quick: document.querySelectorAll('.chat-quick'),
  };
  let _cwLastBody = null;
  function _cwAppend(role, text, actions, results, suggestions){
    if(!_cw.msgs) return;
    const wrap = document.createElement('div');
    const isUser = role === 'you';
    wrap.className = 'flex ' + (isUser ? 'justify-end' : 'justify-start');
    const bubble = document.createElement('div');
    bubble.className = (isUser
      ? 'max-w-[85%] rounded-2xl px-3 py-2 text-white'
      : 'max-w-[85%] rounded-2xl px-3 py-2 border') + ' card';
    bubble.textContent = text;
    if(actions && actions.length){
      const list = document.createElement('div');
      list.className = 'mt-2 flex flex-wrap gap-2 text-xs';
      actions.forEach((action) => {
        if(action.type === 'open_token' && action.token){
          const link = document.createElement('a');
          link.href = '/review/' + action.token;
          link.textContent = 'Öffnen ' + action.token.slice(0,10) + '…';
          link.className = 'rounded-full border px-2 py-1';
          list.appendChild(link);
        } else if(action.type){
          const tag = document.createElement('span');
          tag.textContent = 'Action: ' + action.type;
          tag.className = 'rounded-full border px-2 py-1';
          list.appendChild(tag);
        }
      });
      bubble.appendChild(list);
    }
    if(results && results.length){
      const list = document.createElement('div');
      list.className = 'mt-2 flex flex-wrap gap-2 text-xs';
      results.forEach((row) => {
        const token = row.doc_id || '';
        const label = row.file_name || token || 'Dokument';
        if(token){
          const link = document.createElement('a');
          link.href = '/review/' + token;
          link.textContent = label;
          link.className = 'rounded-full border px-2 py-1';
          list.appendChild(link);
        }
      });
      bubble.appendChild(list);
    }
    if(suggestions && suggestions.length){
      const list = document.createElement('div');
      list.className = 'mt-2 flex flex-wrap gap-2 text-xs';
      suggestions.forEach((s) => {
        const btn = document.createElement('button');
        btn.textContent = s;
        btn.dataset.q = s;
        btn.className = 'rounded-full border px-2 py-1 chat-suggestion';
        list.appendChild(btn);
      });
      bubble.appendChild(list);
    }
    if(isUser){
      bubble.style.background = 'var(--accent-600)';
    }
    wrap.appendChild(bubble);
    _cw.msgs.appendChild(wrap);
    _cw.msgs.scrollTop = _cw.msgs.scrollHeight;
    if(_cw.unread && _cw.drawer?.classList.contains('hidden')){
      _cw.unread.classList.remove('hidden');
    }
  }
  function _cwLoad(){
    try{
      const k = localStorage.getItem('kukanilea_cw_kdnr') || '';
      if(_cw.kdnr) _cw.kdnr.value = k;
      const hist = JSON.parse(localStorage.getItem('kukanilea_cw_hist') || '[]');
      if(_cw.msgs){
        _cw.msgs.innerHTML = '';
        hist.forEach(x => _cwAppend(x.role, x.text));
      }
    }catch(e){}
  }
  function _cwSave(){
    try{
      if(_cw.kdnr) localStorage.setItem('kukanilea_cw_kdnr', _cw.kdnr.value || '');
      const hist = [];
      if(_cw.msgs){
        _cw.msgs.querySelectorAll('div.flex').forEach(row => {
          const isUser = row.className.includes('justify-end');
          const bubble = row.querySelector('div');
          hist.push({role: isUser ? 'you' : 'assistant', text: bubble ? bubble.textContent : ''});
        });
      }
      localStorage.setItem('kukanilea_cw_hist', JSON.stringify(hist.slice(-40)));
    }catch(e){}
  }
  async function _cwPostChat(body, attempts=2){
    let lastErr = null;
    for(let i=0; i<=attempts; i++){
      try{
        const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token': window.KS_CSRF}, body: JSON.stringify(body)});
        let j = {};
        try{ j = await r.json(); }catch(e){}
        if(!r.ok){
          const msg = j.error?.message || j.message || j.error || ('HTTP ' + r.status);
          throw new Error(msg);
        }
        return j;
      }catch(e){
        lastErr = e;
        await new Promise(r => setTimeout(r, 300 * (i + 1)));
      }
    }
    throw lastErr || new Error("Unbekannter Fehler");
  }
  async function _cwSend(){
    const q = (_cw.input && _cw.input.value ? _cw.input.value.trim() : '');
    if(!q) return;
    _cwAppend('you', q);
    if(_cw.input) _cw.input.value = '';
    _cwSave();
    if(_cw.status) _cw.status.textContent = 'Denke…';
    if(_cw.retry) _cw.retry.classList.add('hidden');
    try{
      const body = { q, kdnr: _cw.kdnr ? _cw.kdnr.value.trim() : '', safe_mode: window.KS_SAFE_MODE || false };
      _cwLastBody = body;
      const j = await _cwPostChat(body);
      _cwAppend('assistant', j.message || '(keine Antwort)', j.actions || [], j.results || [], j.suggestions || []);
      if(_cw.status) _cw.status.textContent = j.ok === false ? 'Hinweis' : 'OK';
      _cwSave();
    }catch(e){
      _cwAppend('assistant', 'Fehler: ' + (e && e.message ? e.message : e));
      if(_cw.status) _cw.status.textContent = 'Fehler';
      if(_cw.retry) _cw.retry.classList.remove('hidden');
    }
  }
  if(_cw.msgs){
    _cw.msgs.addEventListener('click', (e) => {
      const btn = e.target.closest('.chat-suggestion');
      if(!btn) return;
      if(_cw.input) _cw.input.value = btn.dataset.q || '';
      _cwSend();
    });
  }
  if(_cw.btn && _cw.drawer){
    _cw.btn.addEventListener('click', () => {
      _cw.drawer.classList.toggle('hidden');
      if(_cw.unread) _cw.unread.classList.add('hidden');
      _cwLoad();
      if(!_cw.drawer.classList.contains('hidden') && _cw.input) _cw.input.focus();
    });
  }
  if(_cw.close) _cw.close.addEventListener('click', () => _cw.drawer && _cw.drawer.classList.add('hidden'));
  if(_cw.send) _cw.send.addEventListener('click', _cwSend);
  if(_cw.input) _cw.input.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ e.preventDefault(); _cwSend(); }});
  if(_cw.kdnr) _cw.kdnr.addEventListener('change', _cwSave);
  if(_cw.clear) _cw.clear.addEventListener('click', () => { if(_cw.msgs) _cw.msgs.innerHTML=''; localStorage.removeItem('kukanilea_cw_hist'); _cwSave(); });
  if(_cw.retry) _cw.retry.addEventListener('click', () => {
    if(!_cwLastBody) return;
    if(_cw.input) _cw.input.value = _cwLastBody.q || '';
    _cwSend();
  });
  _cw.quick?.forEach((btn) => {
    btn.addEventListener('click', () => {
      if(_cw.input) _cw.input.value = btn.dataset.q || '';
      _cwSend();
    });
  });
  // ---- /Floating Chat Widget ----
})();
</script>"""

HTML_TIME = r"""
<div class="grid gap-4">
  <div class="card p-4 rounded-2xl border">
    <div class="text-lg font-semibold mb-2">Time Tracking</div>
    <div class="text-sm opacity-80 mb-4">Lokale Zeiterfassung pro Nutzer (tenant-scoped).</div>
    <div class="grid gap-2 md:grid-cols-3 text-sm">
      <div>
        <label class="block text-xs opacity-70 mb-1">Projekt</label>
        <select id="timeProject" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent"></select>
      </div>
      <div>
        <label class="block text-xs opacity-70 mb-1">Notiz</label>
        <input id="timeNote" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. Angebot telefoniert" />
      </div>
      <div class="flex items-end gap-2">
        <button id="timeStart" class="rounded-xl px-4 py-2 text-sm btn-primary">Start</button>
        <button id="timeStop" class="rounded-xl px-4 py-2 text-sm btn-outline">Stop</button>
      </div>
    </div>
    <div class="mt-3 flex gap-2">
      <input id="timeProjectName" class="rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Neues Projekt" />
      <input id="timeProjectCustomer" class="rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Kunde (optional)" />
      <button id="timeProjectCreate" class="rounded-xl px-3 py-2 text-sm btn-outline">Projekt anlegen</button>
    </div>
    <div id="timeStatus" class="text-xs muted mt-2"></div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="flex items-center justify-between mb-2">
      <div class="text-sm font-semibold">Diese Woche</div>
      <button id="timeExport" class="rounded-xl px-3 py-2 text-xs btn-outline">CSV Export</button>
    </div>
    <div id="timeWeek" class="text-sm"></div>
  </div>
</div>

<script>
(function(){
  const status = document.getElementById('timeStatus');
  const projectSelect = document.getElementById('timeProject');
  const note = document.getElementById('timeNote');
  const weekBox = document.getElementById('timeWeek');

  async function postJson(url, body){
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token': window.KS_CSRF}, body: JSON.stringify(body || {})});
    let j = {};
    try{ j = await r.json(); }catch(e){}
    if(!r.ok){
      throw new Error(j.error?.message || j.message || j.error || ('HTTP ' + r.status));
    }
    return j;
  }

  async function getJson(url){
    const r = await fetch(url, {headers:{'X-CSRF-Token': window.KS_CSRF}});
    let j = {};
    try{ j = await r.json(); }catch(e){}
    if(!r.ok){
      throw new Error(j.error?.message || j.message || j.error || ('HTTP ' + r.status));
    }
    return j;
  }

  function weekStartISO(){
    const now = new Date();
    const day = (now.getDay() + 6) % 7;
    now.setDate(now.getDate() - day);
    return now.toISOString().slice(0,10);
  }

  async function loadProjects(){
    const j = await getJson('/api/time/projects');
    if(projectSelect){
      projectSelect.innerHTML = '';
      (j.projects || []).forEach((p) => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name + (p.customer_name ? ' · ' + p.customer_name : '');
        projectSelect.appendChild(opt);
      });
    }
  }

  async function loadWeek(){
    const j = await getJson('/api/time/week?start=' + weekStartISO());
    if(weekBox){
      if(!j.entries || !j.entries.length){
        weekBox.textContent = 'Keine Einträge.';
        return;
      }
      weekBox.innerHTML = j.entries.map((e) => {
        return `<div class="py-1 border-b border-slate-800">${e.started_at} → ${e.stopped_at || 'läuft'} · ${e.note || ''}</div>`;
      }).join('');
    }
  }

  document.getElementById('timeStart')?.addEventListener('click', async () => {
    try{
      const project_id = projectSelect ? parseInt(projectSelect.value || '0', 10) : 0;
      const j = await postJson('/api/time/start', {project_id, note: note?.value || ''});
      status.textContent = 'Timer läuft (ID ' + j.entry_id + ')';
      await loadWeek();
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });

  document.getElementById('timeStop')?.addEventListener('click', async () => {
    try{
      const j = await postJson('/api/time/stop');
      status.textContent = j.entry_id ? 'Timer gestoppt (ID ' + j.entry_id + ')' : 'Kein aktiver Timer.';
      await loadWeek();
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });

  document.getElementById('timeProjectCreate')?.addEventListener('click', async () => {
    const name = document.getElementById('timeProjectName')?.value || '';
    const customer = document.getElementById('timeProjectCustomer')?.value || '';
    if(!name){ status.textContent = 'Projektname fehlt.'; return; }
    try{
      await postJson('/api/time/projects', {name, customer_name: customer});
      document.getElementById('timeProjectName').value = '';
      document.getElementById('timeProjectCustomer').value = '';
      await loadProjects();
      status.textContent = 'Projekt angelegt.';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });

  document.getElementById('timeExport')?.addEventListener('click', async () => {
    const url = '/api/time/export?start=' + weekStartISO();
    const res = await fetch(url, {headers:{'X-CSRF-Token': window.KS_CSRF}});
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'time_entries.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  });

  loadProjects().then(loadWeek).catch((e) => { status.textContent = 'Fehler: ' + e.message; });
})();
</script>
"""

# -------- Routes / API ----------

# ============================================================
# Auth routes + global guard
# ============================================================
@bp.before_app_request
def _guard_login():
    p = request.path or "/"
    if p.startswith("/static/") or p in ["/login", "/health", "/auth/google/start", "/auth/google/callback", "/api/health", "/api/ping"]:
        return None
    if not current_user():
        if p.startswith("/api/"):
            return json_error("auth_required", "Authentifizierung erforderlich.", status=401)
        return redirect(url_for("web.login", next=p))
    return None


@bp.before_app_request
def _csrf_guard():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path in {"/login"}:
        token = request.form.get("csrf_token")
    else:
        token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    expected = session.get("csrf_token")
    if not expected or not token or token != expected:
        if request.path.startswith("/api/"):
            return json_error("csrf_failed", "CSRF-Token fehlt oder ungültig.", status=403)
        abort(403)
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    nxt = request.args.get("next", "/")
    if request.method == "POST":
        u = (request.form.get("username") or "").strip().lower()
        pw = (request.form.get("password") or "").strip()
        if not u or not pw:
            error = "Bitte Username und Passwort eingeben."
        else:
            user = auth_db.get_user(u)
            if user and user.password_hash == hash_password(pw):
                memberships = auth_db.get_memberships(u)
                if not memberships:
                    error = "Keine Mandanten-Zuordnung gefunden."
                else:
                    membership = memberships[0]
                    login_user(u, membership.role, membership.tenant_id)
                    _audit("login", target=u, meta={"role": membership.role, "tenant": membership.tenant_id})
                    return redirect(nxt or url_for("web.index"))
            else:
                error = "Login fehlgeschlagen."
    return _render_base(render_template_string(HTML_LOGIN, error=error), active_tab="upload")


@bp.get("/auth/google/start")
def google_start():
    if not (current_app.config.get("GOOGLE_CLIENT_ID") and current_app.config.get("GOOGLE_CLIENT_SECRET")):
        return _render_base(_card("info", "Google OAuth ist nicht konfiguriert. Setze GOOGLE_CLIENT_ID/SECRET."), active_tab="mail")
    return _render_base(_card("info", "Google OAuth Flow (Stub). Callback nicht implementiert."), active_tab="mail")


@bp.get("/auth/google/callback")
def google_callback():
    return _render_base(_card("info", "Google OAuth Callback (Stub)."), active_tab="mail")


@bp.route("/logout")
def logout():
    if current_user():
        _audit("logout", target=current_user() or "", meta={})
    logout_user()
    return redirect(url_for("web.login"))


@bp.route("/api/progress/<token>")
def api_progress(token: str):
    if (not current_user()) and (request.remote_addr not in ("127.0.0.1","::1")):
        return json_error("auth_required", "Authentifizierung erforderlich.", status=401)
    p = read_pending(token)
    if not p:
        return json_error("not_found", "Token nicht gefunden.", status=404)
    return jsonify(
        ok=True,
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", "")
    )

def _weather_answer(city: str) -> str:
    info = get_weather(city)
    if not info:
        return f"Ich konnte das Wetter für {city} nicht abrufen."
    return f"Wetter {info.get('city','')}: {info.get('summary','')} (Temp: {info.get('temp_c','?')}°C, Wind: {info.get('wind_kmh','?')} km/h)"


def _weather_adapter(message: str) -> str:
    city = "Berlin"
    match = re.search(r"\bin\s+([A-Za-zÄÖÜäöüß\- ]{2,40})\b", message, re.IGNORECASE)
    if match:
        city = match.group(1).strip()
    return _weather_answer(city)


ORCHESTRATOR = Orchestrator(core, weather_adapter=_weather_adapter)
_DEV_STATUS = {"index": None, "scan": None, "llm": None, "db": None}


def _mock_generate(prompt: str) -> str:
    return f"[mocked] {prompt.strip()[:200]}"


@bp.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """
    JSON in:
      { "q": "...", "kdnr": "1234" (optional), "token": "..." (optional) }

    JSON out:
      { ok: true, message: "...", results: [...], actions: [...], debug: {...} }
    """
    payload = request.get_json(silent=True) or {}
    q = (payload.get("q") or "").strip()
    kdnr = (payload.get("kdnr") or "").strip()
    token = (payload.get("token") or "").strip()
    safe_mode = bool(payload.get("safe_mode"))

    if not chat_limiter.allow(_rate_key()):
        return json_error("rate_limited", "Zu viele Anfragen. Bitte kurz warten.", status=429)
    if not q:
        return json_error("empty_query", "Leer.", status=400)

    user = current_user() or "dev"
    role = current_role()
    auth_db: AuthDB = current_app.extensions["auth_db"]
    auth_db.add_chat_message(
        ts=datetime.utcnow().isoformat(),
        tenant_id=current_tenant(),
        username=str(user),
        role=str(role),
        direction="user",
        message=q,
    )
    context = AgentContext(
        tenant_id=current_tenant(),
        user=str(user),
        role=str(role),
        kdnr=kdnr,
        token=token,
        meta={"safe_mode": safe_mode},
    )
    try:
        with time_limit(5):
            result = ORCHESTRATOR.handle(q, context)
    except TimeoutError:
        return json_error("timeout", "Die Anfrage hat zu lange gedauert.", status=504)
    payload_out = {
        "ok": result.ok,
        "message": result.text,
        "suggestions": result.suggestions or [],
        "results": result.data.get("results", []) if isinstance(result.data, dict) else [],
        "actions": result.actions,
        "error": error_payload(result.error or "error", result.text) if not result.ok else None,
        "request_id": getattr(g, "request_id", None),
    }
    auth_db.add_chat_message(
        ts=datetime.utcnow().isoformat(),
        tenant_id=current_tenant(),
        username=str(user),
        role=str(role),
        direction="assistant",
        message=result.text,
    )
    if current_role() == "DEV":
        payload_out["debug"] = {"intent": result.intent, "data": result.data}
    return jsonify(payload_out)


@bp.post("/api/search")
@login_required
def api_search():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    kdnr = (payload.get("kdnr") or "").strip()
    limit = int(payload.get("limit") or 8)
    if not query:
        return json_error("missing_query", "Query fehlt.", status=400)
    if not search_limiter.allow(_rate_key()):
        return json_error("rate_limited", "Zu viele Suchanfragen. Bitte kurz warten.", status=429)
    context = AgentContext(
        tenant_id=current_tenant(),
        user=str(current_user() or "dev"),
        role=str(current_role()),
        kdnr=kdnr,
    )
    agent = SearchAgent(core)
    results, suggestions = agent.search(query, context, limit=limit)
    message = "OK" if results else "Keine Treffer gefunden."
    return jsonify(ok=True, message=message, results=results, did_you_mean=suggestions or [])


@bp.post("/api/customer")
@login_required
@require_role("OPERATOR")
def api_customer():
    payload = request.get_json(silent=True) or {}
    kdnr = (payload.get("kdnr") or "").strip()
    if not kdnr:
        return json_error("missing_kdnr", "KDNR fehlt.", status=400)
    context = AgentContext(
        tenant_id=current_tenant(),
        user=str(current_user() or "dev"),
        role=str(current_role()),
        kdnr=kdnr,
    )
    agent = CustomerAgent(core)
    result = agent.handle(kdnr, "customer_lookup", context)
    results = result.data.get("results", []) if isinstance(result.data, dict) else []
    summary = results[0] if results else {}
    return jsonify(
        ok=result.error is None,
        kdnr=str(summary.get("kdnr") or kdnr),
        customer_name=str(summary.get("customer_name") or ""),
        last_doc=str(summary.get("file_name") or ""),
        last_doc_date=str(summary.get("doc_date") or ""),
        results=results,
        message=result.text,
    )


@bp.get("/api/tasks")
@login_required
def api_tasks():
    status = (request.args.get("status") or "OPEN").strip().upper()
    if callable(task_list):
        tasks = task_list(tenant=current_tenant(), status=status, limit=200)  # type: ignore
    else:
        tasks = []
    return jsonify(ok=True, tasks=tasks)


@bp.post("/api/tasks")
@login_required
@require_role("OPERATOR")
def api_task_create():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    details = (payload.get("details") or "").strip()
    if not title:
        return json_error("missing_title", "Titel fehlt.", status=400)
    if not callable(getattr(core, "task_create", None)):
        return json_error("tasks_unavailable", "Task-System nicht verfügbar.", status=400)
    task_id = core.task_create(
        tenant=current_tenant() or "default",
        severity="INFO",
        task_type="CHAT",
        title=title,
        details=details,
        created_by=current_user() or "",
    )
    _audit("task_create", target=str(task_id), meta={"title": title})
    return jsonify(ok=True, task_id=task_id)


@bp.get("/api/time/projects")
@login_required
@require_role("OPERATOR")
def api_time_projects():
    if not callable(getattr(core, "time_project_list", None)):
        return json_error("time_unavailable", "Zeiterfassung nicht verfügbar.", status=400)
    projects = core.time_project_list(tenant=current_tenant())
    return jsonify(ok=True, projects=projects)


@bp.post("/api/time/projects")
@login_required
@require_role("OPERATOR")
def api_time_project_create():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    customer_name = (payload.get("customer_name") or "").strip()
    if not name:
        return json_error("missing_name", "Projektname fehlt.", status=400)
    if not callable(getattr(core, "time_project_create", None)):
        return json_error("time_unavailable", "Zeiterfassung nicht verfügbar.", status=400)
    project_id = core.time_project_create(tenant=current_tenant(), name=name, customer_name=customer_name)
    _audit("time_project_create", target=str(project_id), meta={"name": name})
    return jsonify(ok=True, project_id=project_id)


@bp.post("/api/time/start")
@login_required
@require_role("OPERATOR")
def api_time_start():
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    note = (payload.get("note") or "").strip()
    if not callable(getattr(core, "time_entry_start", None)):
        return json_error("time_unavailable", "Zeiterfassung nicht verfügbar.", status=400)
    entry_id = core.time_entry_start(
        tenant=current_tenant(),
        username=current_user() or "",
        project_id=int(project_id) if project_id else None,
        note=note,
    )
    _audit("time_entry_start", target=str(entry_id), meta={"project_id": project_id})
    return jsonify(ok=True, entry_id=entry_id)


@bp.post("/api/time/stop")
@login_required
@require_role("OPERATOR")
def api_time_stop():
    if not callable(getattr(core, "time_entry_stop", None)):
        return json_error("time_unavailable", "Zeiterfassung nicht verfügbar.", status=400)
    entry_id = core.time_entry_stop(tenant=current_tenant(), username=current_user() or "")
    _audit("time_entry_stop", target=str(entry_id or ""))
    return jsonify(ok=True, entry_id=entry_id)


@bp.get("/api/time/week")
@login_required
@require_role("OPERATOR")
def api_time_week():
    start = (request.args.get("start") or "").strip()
    if not start:
        return json_error("missing_start", "Startdatum fehlt.", status=400)
    if not callable(getattr(core, "time_entry_list_week", None)):
        return json_error("time_unavailable", "Zeiterfassung nicht verfügbar.", status=400)
    entries = core.time_entry_list_week(tenant=current_tenant(), username=current_user() or "", week_start=start)
    return jsonify(ok=True, entries=entries)


@bp.get("/api/time/export")
@login_required
@require_role("OPERATOR")
def api_time_export():
    start = (request.args.get("start") or "").strip()
    if not start:
        return json_error("missing_start", "Startdatum fehlt.", status=400)
    if not callable(getattr(core, "time_entry_export_csv", None)):
        return json_error("time_unavailable", "Zeiterfassung nicht verfügbar.", status=400)
    csv_data = core.time_entry_export_csv(tenant=current_tenant(), username=current_user() or "", week_start=start)
    return current_app.response_class(csv_data, mimetype="text/csv")


@bp.get("/api/audit")
@login_required
@require_role("ADMIN")
def api_audit():
    limit = int(request.args.get("limit") or 100)
    if callable(getattr(core, "audit_list", None)):
        events = core.audit_list(tenant_id=current_tenant(), limit=limit)
    else:
        events = []
    return jsonify(ok=True, events=events)


# ==============================
# Mail Agent Tab (Template/Mock workflow)
# ==============================
HTML_MAIL = """
<div class="grid gap-4">
  <div class="card p-4 rounded-2xl border">
    <div class="flex items-center justify-between">
      <div>
        <div class="text-lg font-semibold">Google Mail (Stub)</div>
        <div class="text-sm opacity-80">OAuth Platzhalter – keine echte Verbindung in dieser Version.</div>
      </div>
      <div class="text-right text-xs opacity-70">
        Status: {{ 'konfiguriert' if google_configured else 'nicht konfiguriert' }}
      </div>
    </div>
    <div class="mt-3 flex gap-2">
      <a class="rounded-xl px-4 py-2 text-sm btn-outline" href="/auth/google/start">Connect Google</a>
      <span class="text-xs opacity-70">Setze GOOGLE_CLIENT_ID/SECRET um den Flow zu aktivieren.</span>
    </div>
  </div>
  <div class="card p-4 rounded-2xl border">
    <div class="text-lg font-semibold mb-1">Mail Agent</div>
    <div class="text-sm opacity-80 mb-4">Entwurf lokal mit Template/Mock-LLM. Keine Drittanbieter-Links.</div>

    <div class="grid gap-3 md:grid-cols-2">
      <div>
        <label class="block text-xs opacity-70 mb-1">Empfänger (optional)</label>
        <input id="m_to" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. haendler@firma.de" />
      </div>
      <div>
        <label class="block text-xs opacity-70 mb-1">Betreff (optional)</label>
        <input id="m_subj" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. Mangel: Defekte Fliesenlieferung" />
      </div>

      <div>
        <label class="block text-xs opacity-70 mb-1">Ton</label>
        <select id="m_tone" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent">
          <option value="neutral" selected>Neutral</option>
          <option value="freundlich">Freundlich</option>
          <option value="formell">Formell</option>
          <option value="bestimmt">Bestimmt (Reklamation)</option>
          <option value="kurz">Sehr kurz</option>
        </select>
      </div>
      <div>
        <label class="block text-xs opacity-70 mb-1">Länge</label>
        <select id="m_len" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent">
          <option value="kurz" selected>Kurz</option>
          <option value="normal">Normal</option>
          <option value="detailliert">Detailliert</option>
        </select>
      </div>

      <div class="md:col-span-2">
        <label class="block text-xs opacity-70 mb-1">Kontext / Stichpunkte</label>
        <textarea id="m_ctx" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent h-32" placeholder="z.B. Bitte Fotos an Händler schicken, Rabatt anfragen, Lieferung vom ... (Details)"></textarea>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <button id="m_gen" class="rounded-xl px-4 py-2 text-sm card btn-primary">Entwurf erzeugen</button>
      <button id="m_copy" class="rounded-xl px-4 py-2 text-sm btn-outline" disabled>Copy</button>
      <button id="m_eml" class="rounded-xl px-4 py-2 text-sm btn-outline" disabled>.eml Export</button>
      <button id="m_rewrite" class="rounded-xl px-4 py-2 text-sm btn-outline">Stil verbessern</button>
      <div class="text-xs opacity-70 flex items-center" id="m_status"></div>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="flex items-center justify-between mb-2">
      <div class="font-semibold">Output</div>
      <div class="text-xs opacity-70">Kopie: Betreff + Body</div>
    </div>
    <textarea id="m_out" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent h-[360px]" placeholder="Hier erscheint der Entwurf…"></textarea>
  </div>
</div>

<script>
(function(){
  const gen=document.getElementById('m_gen');
  const copy=document.getElementById('m_copy');
  const rewrite=document.getElementById('m_rewrite');
  const eml=document.getElementById('m_eml');
  const status=document.getElementById('m_status');
  const out=document.getElementById('m_out');

  function v(id){ return (document.getElementById(id)?.value||'').trim(); }

  async function run(){
    status.textContent='Generiere…';
    out.value='';
    copy.disabled=true;
    if(eml) eml.disabled=true;
    try{
      const res = await fetch('/api/mail/draft', {
        method:'POST',
        headers:{'Content-Type':'application/json', 'X-CSRF-Token': window.KS_CSRF},
        body: JSON.stringify({
          to: v('m_to'),
          subject: v('m_subj'),
          tone: v('m_tone'),
          length: v('m_len'),
          context: v('m_ctx')
        })
      });
      const data = await res.json();
      if(!res.ok){
        status.textContent = 'Fehler: ' + (data.error?.message || data.error || res.status);
        return;
      }
      out.value = data.text || '';
      copy.disabled = !out.value;
      if(eml) eml.disabled = !out.value;
      status.textContent = data.meta || 'OK';
    }catch(e){
      status.textContent='Fehler: '+e;
    }
  }

  async function doCopy(){
    try{
      await navigator.clipboard.writeText(out.value||'');
      status.textContent='In Zwischenablage kopiert.';
    }catch(e){
      status.textContent='Copy fehlgeschlagen (Browser-Rechte).';
    }
  }

  async function doEml(){
    if(!out.value) return;
    const payload = { to: v('m_to'), subject: v('m_subj'), body: out.value };
    const res = await fetch('/api/mail/eml', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token': window.KS_CSRF}, body: JSON.stringify(payload)});
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kukanilea_mail.eml';
    a.click();
    URL.revokeObjectURL(url);
  }

  function rewriteLocal(){
    if(!out.value) return;
    const lines = out.value.split('\\n').map(l => l.trim()).filter(Boolean);
    const greeting = lines[0]?.startsWith('Betreff') ? '' : 'Guten Tag,';
    const closing = 'Mit freundlichen Grüßen';
    const body = lines.filter(l => !l.toLowerCase().startsWith('betreff')).join('\\n');
    out.value = [greeting, body, '', closing].filter(Boolean).join('\\n');
    status.textContent='Stil verbessert (lokal).';
  }

  gen && gen.addEventListener('click', run);
  copy && copy.addEventListener('click', doCopy);
  rewrite && rewrite.addEventListener('click', rewriteLocal);
  eml && eml.addEventListener('click', doEml);
})();
</script>
"""

HTML_SETTINGS = """
<div class="grid gap-4">
  <div class="card p-4 rounded-2xl border">
    <div class="text-lg font-semibold mb-2">DEV Settings</div>
    <div class="grid gap-3 md:grid-cols-2 text-sm">
      <div>
        <div class="muted text-xs mb-1">Profile</div>
        <div><strong>{{ profile.name }}</strong></div>
        <div class="muted text-xs">Base Path: {{ profile.base_path }}</div>
      </div>
      <div>
        <div class="muted text-xs mb-1">Core DB</div>
        <div><strong>{{ core_db.path }}</strong></div>
        <div class="muted text-xs">Schema: {{ core_db.schema_version }} · Tenants: {{ core_db.tenants }}</div>
      </div>
      <div>
        <div class="muted text-xs mb-1">Auth DB</div>
        <div><strong>{{ auth_db_path }}</strong></div>
        <div class="muted text-xs">Schema: {{ auth_schema }} · Tenants: {{ auth_tenants }}</div>
      </div>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">DB wechseln (Allowlist)</div>
    <div class="flex flex-wrap gap-2 items-center">
      <select id="dbSelect" class="rounded-xl border px-3 py-2 text-sm bg-transparent">
        {% for p in db_files %}
          <option value="{{ p }}">{{ p }}</option>
        {% endfor %}
      </select>
      <button id="dbSwitch" class="rounded-xl px-3 py-2 text-sm btn-primary">DB wechseln</button>
      <span id="dbSwitchStatus" class="text-xs muted"></span>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">Ablage-Pfad wechseln (DEV)</div>
    <div class="flex flex-wrap gap-2 items-center">
      <select id="baseSelect" class="rounded-xl border px-3 py-2 text-sm bg-transparent">
        {% for p in base_paths %}
          <option value="{{ p }}">{{ p }}</option>
        {% endfor %}
      </select>
      <input id="baseCustom" class="rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Benutzerdefinierter Pfad" />
      <button id="baseSwitch" class="rounded-xl px-3 py-2 text-sm btn-primary">Ablage wechseln</button>
      <span id="baseSwitchStatus" class="text-xs muted"></span>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">Tools</div>
    <div class="flex flex-wrap gap-2">
      <button id="seedUsers" class="rounded-xl px-3 py-2 text-sm btn-outline">Seed Dev Users</button>
      <button id="rebuildIndex" class="rounded-xl px-3 py-2 text-sm btn-outline">Rebuild Index</button>
      <button id="fullScan" class="rounded-xl px-3 py-2 text-sm btn-outline">Full Scan</button>
      <button id="repairDrift" class="rounded-xl px-3 py-2 text-sm btn-outline">Repair Drift Scan</button>
      <button id="testLLM" class="rounded-xl px-3 py-2 text-sm btn-outline">Test LLM</button>
    </div>
    <div id="toolStatus" class="text-xs muted mt-2"></div>
  </div>
</div>

<script>
(function(){
  async function postJson(url, body){
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token': window.KS_CSRF}, body: JSON.stringify(body || {})});
    let j = {};
    try{ j = await r.json(); }catch(e){}
    if(!r.ok){
      throw new Error(j.error?.message || j.message || j.error || ('HTTP ' + r.status));
    }
    return j;
  }

  const status = document.getElementById('toolStatus');
  const dbStatus = document.getElementById('dbSwitchStatus');
  const baseStatus = document.getElementById('baseSwitchStatus');

  document.getElementById('seedUsers')?.addEventListener('click', async () => {
    status.textContent = 'Seeding...';
    try{
      const j = await postJson('/api/dev/seed-users');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('rebuildIndex')?.addEventListener('click', async () => {
    status.textContent = 'Rebuild läuft...';
    try{
      const j = await postJson('/api/dev/rebuild-index');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('fullScan')?.addEventListener('click', async () => {
    status.textContent = 'Scan läuft...';
    try{
      const j = await postJson('/api/dev/full-scan');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('repairDrift')?.addEventListener('click', async () => {
    status.textContent = 'Drift-Scan läuft...';
    try{
      const j = await postJson('/api/dev/repair-drift');
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('testLLM')?.addEventListener('click', async () => {
    status.textContent = 'Teste LLM...';
    try{
      const j = await postJson('/api/dev/test-llm', {q:'suche rechnung von gerd'});
      status.textContent = j.message || 'OK';
    }catch(e){ status.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('dbSwitch')?.addEventListener('click', async () => {
    const sel = document.getElementById('dbSelect');
    const path = sel ? sel.value : '';
    if(!path){ return; }
    dbStatus.textContent = 'Wechsle...';
    try{
      const j = await postJson('/api/dev/switch-db', {path});
      dbStatus.textContent = j.message || 'OK';
      window.location.reload();
    }catch(e){ dbStatus.textContent = 'Fehler: ' + e.message; }
  });
  document.getElementById('baseSwitch')?.addEventListener('click', async () => {
    const sel = document.getElementById('baseSelect');
    const custom = document.getElementById('baseCustom');
    const path = (custom && custom.value ? custom.value : (sel ? sel.value : ''));
    if(!path){ return; }
    baseStatus.textContent = 'Wechsle...';
    try{
      const j = await postJson('/api/dev/switch-base', {path});
      baseStatus.textContent = j.message || 'OK';
      window.location.reload();
    }catch(e){ baseStatus.textContent = 'Fehler: ' + e.message; }
  });
})();
</script>
"""

def _mail_prompt(to: str, subject: str, tone: str, length: str, context: str) -> str:
    return f"""Du bist ein deutscher Office-Assistent. Schreibe einen professionellen E-Mail-Entwurf.
Wichtig:
- Du hast KEINEN Zugriff auf echte Systeme. Keine falschen Behauptungen.
- Klar, freundlich, ohne leere Floskeln.
- Wenn Fotos erwähnt werden: Bitte um Bestätigung, dass Fotos angehängt sind und nenne die Anzahl falls bekannt.
- Output-Format exakt:
BETREFF: <eine Zeile>
TEXT:
<Mailtext>

Empfänger: {to or '(nicht angegeben)'}
Betreff-Vorschlag (falls vorhanden): {subject or '(leer)'}
Ton: {tone}
Länge: {length}

Kontext/Stichpunkte:
{context or '(leer)'}
"""

@bp.get("/mail")
@login_required
def mail_page():
    google_configured = bool(current_app.config.get("GOOGLE_CLIENT_ID") and current_app.config.get("GOOGLE_CLIENT_SECRET"))
    return _render_base(render_template_string(HTML_MAIL, google_configured=google_configured), active_tab="mail")


@bp.get("/settings")
@login_required
@require_role("DEV")
def settings_page():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    if callable(getattr(core, "get_db_info", None)):
        core_db = core.get_db_info()
    else:
        core_db = {"path": str(getattr(core, "DB_PATH", "")), "schema_version": "?", "tenants": "?"}
    return _render_base(
        render_template_string(
            HTML_SETTINGS,
            core_db=core_db,
            auth_db_path=str(auth_db.path),
            auth_schema=auth_db.get_schema_version(),
            auth_tenants=auth_db.count_tenants(),
            db_files=[str(p) for p in _list_allowlisted_db_files()],
            base_paths=[str(p) for p in _list_allowlisted_base_paths()],
            profile=_get_profile(),
        ),
        active_tab="settings",
    )


@bp.post("/api/dev/seed-users")
@login_required
@require_role("DEV")
def api_seed_users():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    msg = _seed_dev_users(auth_db)
    _audit("seed_users", meta={"status": "ok"})
    return jsonify(ok=True, message=msg)


@bp.post("/api/dev/rebuild-index")
@login_required
@require_role("DEV")
def api_rebuild_index():
    if callable(getattr(core, "index_rebuild", None)):
        result = core.index_rebuild()
    elif callable(getattr(core, "index_run_full", None)):
        result = core.index_run_full()
    else:
        return json_error("index_unavailable", "Indexing nicht verfügbar.", status=400)
    _DEV_STATUS["index"] = result
    _audit("rebuild_index", meta={"result": result})
    return jsonify(ok=True, message="Index neu aufgebaut.", result=result)


@bp.post("/api/dev/full-scan")
@login_required
@require_role("DEV")
def api_full_scan():
    if callable(getattr(core, "index_run_full", None)):
        result = core.index_run_full()
    else:
        return json_error("scan_unavailable", "Scan nicht verfügbar.", status=400)
    _DEV_STATUS["scan"] = result
    _audit("full_scan", meta={"result": result})
    return jsonify(ok=True, message="Scan abgeschlossen.", result=result)


@bp.post("/api/dev/repair-drift")
@login_required
@require_role("DEV")
def api_repair_drift():
    if callable(getattr(core, "index_run_full", None)):
        result = core.index_run_full()
    else:
        return json_error("drift_scan_unavailable", "Drift-Scan nicht verfügbar.", status=400)
    _DEV_STATUS["scan"] = result
    _audit("repair_drift", meta={"result": result})
    return jsonify(ok=True, message="Drift-Scan abgeschlossen.", result=result)


@bp.post("/api/dev/switch-db")
@login_required
@require_role("DEV")
def api_switch_db():
    payload = request.get_json(silent=True) or {}
    path = Path(str(payload.get("path", ""))).expanduser()
    if not path:
        return json_error("missing_path", "Pfad fehlt.", status=400)
    if not _is_allowlisted_path(path):
        return json_error("path_not_allowed", "Pfad nicht erlaubt.", status=400)
    if not path.exists():
        return json_error("path_not_found", "Datei existiert nicht.", status=400)
    old_path = str(getattr(core, "DB_PATH", ""))
    if callable(getattr(core, "set_db_path", None)):
        core.set_db_path(path)
        _DEV_STATUS["db"] = {"old": old_path, "new": str(path)}
        _audit("switch_db", target=str(path), meta={"old": old_path})
        return jsonify(ok=True, message="DB gewechselt.", path=str(path))
    return json_error("db_switch_unavailable", "DB switch nicht verfügbar.", status=400)


@bp.post("/api/dev/switch-base")
@login_required
@require_role("DEV")
def api_switch_base():
    payload = request.get_json(silent=True) or {}
    path = Path(str(payload.get("path", ""))).expanduser()
    if not path:
        return json_error("missing_path", "Pfad fehlt.", status=400)
    if not _is_storage_path_valid(path):
        return json_error("path_not_allowed", "Pfad nicht erlaubt oder nicht vorhanden.", status=400)
    old_path = str(getattr(core, "BASE_PATH", ""))
    if callable(getattr(core, "set_base_path", None)):
        core.set_base_path(path)
        global BASE_PATH
        BASE_PATH = path
        _DEV_STATUS["base"] = {"old": old_path, "new": str(path)}
        _audit("switch_base", target=str(path), meta={"old": old_path})
        return jsonify(ok=True, message="Ablage gewechselt.", path=str(path))
    return json_error("base_switch_unavailable", "Ablage switch nicht verfügbar.", status=400)


@bp.post("/api/dev/test-llm")
@login_required
@require_role("DEV")
def api_test_llm():
    payload = request.get_json(silent=True) or {}
    q = str(payload.get("q") or "suche rechnung")
    llm = getattr(ORCHESTRATOR, "llm", None)
    if not llm:
        return json_error("llm_unavailable", "LLM nicht verfügbar.", status=400)
    result = llm.rewrite_query(q)
    _DEV_STATUS["llm"] = result
    _audit("test_llm", meta={"result": result})
    return jsonify(ok=True, message=f"LLM: {llm.name}, intent={result.get('intent')}")

@bp.post("/api/mail/draft")
@login_required
def api_mail_draft():
    try:
        payload = request.get_json(force=True) or {}
        to = (payload.get("to") or "").strip()
        subject = (payload.get("subject") or "").strip()
        tone = (payload.get("tone") or "neutral").strip()
        length = (payload.get("length") or "kurz").strip()
        context = (payload.get("context") or "").strip()

        if not context and not subject:
            return json_error("missing_context", "Bitte Kontext oder Betreff angeben.", status=400)

        text = _mock_generate(_mail_prompt(to, subject, tone, length, context))
        return jsonify({"ok": True, "text": text, "meta": "mode=mock"}), 200
    except Exception as e:
        return json_error("mail_draft_failed", "Mail-Entwurf fehlgeschlagen.", status=500, details={"reason": str(e)})


@bp.post("/api/mail/eml")
@login_required
def api_mail_eml():
    payload = request.get_json(force=True) or {}
    to = (payload.get("to") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    if not body:
        return json_error("missing_body", "Body fehlt.", status=400)
    import email.message
    msg = email.message.EmailMessage()
    msg["To"] = to or "unknown@example.com"
    msg["From"] = "noreply@kukanilea.local"
    msg["Subject"] = subject or "KUKANILEA Entwurf"
    msg.set_content(body)
    eml_bytes = msg.as_bytes()
    return current_app.response_class(eml_bytes, mimetype="message/rfc822")



@bp.route("/")
def index():
    items_meta = list_pending() or []
    items = [x.get("_token") for x in items_meta if x.get("_token")]
    meta = {}
    for it in items_meta:
        t = it.get("_token")
        if t:
            meta[t] = {"filename": it.get("filename",""), "progress": float(it.get("progress",0.0) or 0.0), "progress_phase": it.get("progress_phase","")}
    return _render_base(render_template_string(HTML_INDEX, items=items, meta=meta), active_tab="upload")

@bp.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return json_error("no_file", "Keine Datei hochgeladen.", status=400)
    if not upload_limiter.allow(_rate_key()):
        return json_error("rate_limited", "Zu viele Uploads. Bitte kurz warten.", status=429)
    tenant = _norm_tenant(current_tenant() or "default")
    # tenant is fixed by license/account; no user input here.
    filename = _safe_filename(f.filename)
    if not _is_allowed_ext(filename):
        return json_error("unsupported", "Dateityp nicht unterstützt.", status=400)
    tenant_in = (EINGANG / tenant)
    tenant_in.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = tenant_in / f"{ts}__{filename}"
    f.save(dest)
    token = analyze_to_pending(dest)
    try:
        p = read_pending(token) or {}
        p["tenant"] = tenant
        w = _wizard_get(p)
        w["tenant"] = tenant
        p["wizard"] = w
        write_pending(token, p)
    except Exception:
        pass
    return jsonify(token=token, tenant=tenant)

@bp.route("/review/<token>/delete", methods=["POST"])
def review_delete(token: str):
    try:
        delete_pending(token)
    except Exception:
        pass
    return redirect(url_for("web.index"))

@bp.route("/file/<token>")
def file_preview(token: str):
    p = read_pending(token)
    if not p:
        abort(404)
    file_path = Path(p.get("path", ""))
    if not file_path.exists():
        abort(404)
    if not _is_allowed_path(file_path):
        abort(403)
    return send_file(file_path, as_attachment=False)

@bp.route("/review/<token>/kdnr", methods=["GET","POST"])
def review(token: str):
    p = read_pending(token)
    if not p:
        return _render_base(_card("error", "Nicht gefunden."), active_tab="upload")
    if p.get("status") == "ANALYZING":
        right = _card("info", "Analyse läuft noch. Bitte kurz warten oder zurück zur Übersicht.")
        return _render_base(
            render_template_string(
                HTML_REVIEW_SPLIT,
                token=token,
                filename=p.get("filename", ""),
                is_pdf=True,
                is_text=False,
                preview="",
                right=right,
                w=_wizard_get(p),
                suggested_doctype="SONSTIGES",
                suggested_date="",
                confidence=0,
            ),
            active_tab="upload",
        )

    w = _wizard_get(p)
    if True:
        # Tenant is fixed per account/license
        w["tenant"] = _norm_tenant(current_tenant() or p.get("tenant", "") or "default")

    suggested_doctype = (p.get("doctype_suggested") or "SONSTIGES").upper()
    if not w.get("doctype"):
        w["doctype"] = suggested_doctype if suggested_doctype in DOCTYPE_CHOICES else "SONSTIGES"
    suggested_date = (p.get("doc_date_suggested") or "").strip()
    confidence = 40
    if suggested_doctype and suggested_doctype != "SONSTIGES":
        confidence += 20
    if suggested_date:
        confidence += 20
    if w.get("kdnr"):
        confidence += 20
    confidence = min(95, confidence)

    # Suggest an existing customer folder (best effort)
    existing_folder_hint = ""
    existing_folder_score = 0.0
    if not (w.get("existing_folder") or "").strip():
        match_path, match_score = suggest_existing_folder(BASE_PATH, w["tenant"], w.get("kdnr",""), w.get("name",""))
        if match_path:
            w["existing_folder"] = match_path
            existing_folder_hint = match_path
            existing_folder_score = match_score

    msg = ""
    if request.method == "POST":
        if request.form.get("reextract") == "1":
            src = Path(p.get("path",""))
            if src.exists():
                try: delete_pending(token)
                except Exception: pass
                new_token = analyze_to_pending(src)
                return redirect(url_for("web.review", token=new_token))
            msg = "Quelle nicht gefunden – Re-Extract nicht möglich."

        if request.form.get("confirm") == "1":
            tenant = _norm_tenant(current_tenant() or w.get("tenant") or "default")
            terr = None
            if terr:
                msg = f"Mandant-Fehler: {terr}"
            else:
                w["tenant"] = tenant
                w["kdnr"] = normalize_component(request.form.get("kdnr") or "")
                w["doctype"] = (request.form.get("doctype") or w.get("doctype") or "SONSTIGES").upper()
                w["document_date"] = normalize_component(request.form.get("document_date") or "")
                w["name"] = normalize_component(request.form.get("name") or "")
                w["addr"] = normalize_component(request.form.get("addr") or "")
                w["plzort"] = normalize_component(request.form.get("plzort") or "")
                w["use_existing"] = normalize_component(request.form.get("use_existing") or "")

                if not w["kdnr"]:
                    msg = "KDNR fehlt."
                else:
                    src = Path(p.get("path",""))
                    if not src.exists():
                        msg = "Datei im Eingang nicht gefunden."
                    else:
                        answers = {
                            "tenant": w["tenant"],
                            "kdnr": w["kdnr"],
                            "use_existing": w.get("use_existing",""),
                            "name": w.get("name") or "Kunde",
                            "addr": w.get("addr") or "Adresse",
                            "plzort": w.get("plzort") or "PLZ Ort",
                            "doctype": w.get("doctype") or "SONSTIGES",
                            "document_date": w.get("document_date") or "",
                        }
                        try:
                            folder, final_path, created_new = process_with_answers(Path(p.get("path","")), answers)
                            write_done(token, {"final_path": str(final_path), **answers})
                            delete_pending(token)
                            return redirect(url_for("web.done_view", token=token))
                        except Exception as e:
                            msg = f"Ablage fehlgeschlagen: {e}"

    _wizard_save(token, p, w)

    filename = p.get("filename","")
    ext = Path(filename).suffix.lower()
    is_pdf = ext == ".pdf"
    is_text = ext == ".txt"

    right = render_template_string(
        HTML_WIZARD,
        w=w,
        doctypes=DOCTYPE_CHOICES,
        suggested_doctype=suggested_doctype,
        suggested_date=suggested_date,
        extracted_text=p.get("extracted_text", ""),
        msg=msg,
        existing_folder_hint=existing_folder_hint,
        existing_folder_score=f"{existing_folder_score:.2f}" if existing_folder_hint else "",
    )
    return _render_base(
        render_template_string(
            HTML_REVIEW_SPLIT,
            token=token,
            filename=filename,
            is_pdf=is_pdf,
            is_text=is_text,
            preview=p.get("preview", ""),
            right=right,
            w=w,
            suggested_doctype=suggested_doctype,
            suggested_date=suggested_date,
            confidence=confidence,
        ),
        active_tab="upload",
    )

@bp.route("/done/<token>")
def done_view(token: str):
    d = read_done(token) or {}
    fp = d.get("final_path","")
    html = f"""<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card'>
      <div class='text-2xl font-bold mb-2'>Fertig</div>
      <div class='muted text-sm mb-4'>Datei wurde abgelegt.</div>
      <div class='muted text-xs'>Pfad</div>
      <div class='text-sm break-all accentText'>{fp}</div>
      <div class='mt-4'><a class='rounded-xl px-4 py-2 font-semibold btn-primary' href='/'>Zur Übersicht</a></div>
    </div>"""
    return _render_base(html, active_tab="upload")

@bp.route("/assistant")
def assistant():
    # Ensure core searches within current tenant
    try:
        import kukanilea_core_v3_fixed as _core
        _core.TENANT_DEFAULT = current_tenant() or _core.TENANT_DEFAULT
    except Exception:
        pass
    q = normalize_component(request.args.get("q","") or "")
    kdnr = normalize_component(request.args.get("kdnr","") or "")
    results = []
    if q and assistant_search is not None:
        try:
            raw = assistant_search(query=q, kdnr=kdnr, limit=50, role=current_role(), tenant_id=current_tenant())
            for r in raw or []:
                fp = r.get("file_path") or ""
                if ASSISTANT_HIDE_EINGANG and fp:
                    try:
                        if str(Path(fp).resolve()).startswith(str(EINGANG.resolve()) + os.sep):
                            continue
                    except Exception:
                        pass
                r["fp_b64"] = _b64(fp) if fp else ""
                results.append(r)
        except Exception:
            pass
    html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
      <div class='text-lg font-semibold mb-1'>Assistant</div>
      <form method='get' class='flex flex-col md:flex-row gap-2 mb-4'>
        <input class='w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input' name='q' value='{q}' placeholder='Suche…' />
        <input class='w-full md:w-40 rounded-xl bg-slate-800 border border-slate-700 p-2 input' name='kdnr' value='{kdnr}' placeholder='Kdnr optional' />
        <button class='rounded-xl px-4 py-2 font-semibold btn-primary md:w-40' type='submit'>Suchen</button>
      </form>
      <div class='muted text-xs'>Treffer: {n}</div>
    </div>""".format(q=q.replace("'", "&#39;"), kdnr=kdnr.replace("'", "&#39;"), n=len(results))
    return _render_base(html, active_tab="assistant")

@bp.route("/tasks")
def tasks():
    available = callable(task_list)
    if not available:
        html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
          <div class='text-lg font-semibold'>Tasks</div>
          <div class='muted text-sm mt-2'>Tasks sind im Core nicht verfügbar.</div>
        </div>"""
        return _render_base(html, active_tab="tasks")
    try:
        items = task_list(status="OPEN", limit=100)  # type: ignore
    except Exception:
        items = []
    html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
      <div class='text-lg font-semibold'>Tasks</div>
      <div class='muted text-xs mt-1'>Offen: {n}</div>
    </div>""".format(n=len(items))
    return _render_base(html, active_tab="tasks")

@bp.route("/time")
@login_required
@require_role("OPERATOR")
def time_tracking():
    return _render_base(HTML_TIME, active_tab="time")

@bp.route("/chat")
def chat():
    return _render_base(HTML_CHAT, active_tab="chat")

@bp.route("/health")
def health():
    return jsonify(ok=True, ts=time.time(), app="kukanilea_upload_v3_ui")
