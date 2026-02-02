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
    - tries Ollama (http://127.0.0.1:11434) if available
    - fallback: uses assistant_search results as "chat-like" answer

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
import urllib.request
import time
import base64
# Optional weather plugin
try:
    from kukanilea_weather_plugin import get_weather  # type: ignore
except Exception:
    get_weather = None  # type: ignore

from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

from flask import (
    Flask, request, jsonify, render_template_string, send_file, abort,
    redirect, url_for, session
)

try:
    from werkzeug.utils import secure_filename
except Exception:
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

rbac_verify_user = _core_get("rbac_verify_user")
rbac_create_user = _core_get("rbac_create_user")
rbac_assign_role = _core_get("rbac_assign_role")
rbac_get_user_roles = _core_get("rbac_get_user_roles")

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
APP = Flask(__name__)
APP.secret_key = os.environ.get("KUKANILEA_SECRET", "kukanilea-dev-secret-change-me")
PORT = int(os.environ.get("PORT", 5051))
APP.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("KUKANILEA_MAX_UPLOAD", str(25 * 1024 * 1024)))

BOOTSTRAP_ADMIN_USER = os.environ.get("KUKANILEA_ADMIN_USER", "").strip().lower()
BOOTSTRAP_ADMIN_PASS = os.environ.get("KUKANILEA_ADMIN_PASS", "").strip()

# Tenant config (UI-level)
TENANT_DEFAULT = os.environ.get("KUKANILEA_TENANT_DEFAULT", "KUKANILEA").strip()
TENANT_FIXED = (os.environ.get("KUKANILEA_TENANT_FIXED", "1").strip().lower() not in ("", "0", "false", "no"))  # default: fixed
# --- Early template defaults (avoid NameError during debug reload) ---
HTML_LOGIN = ""  # will be overwritten later by the full template block

def _current_tenant() -> str:
    """Return the active tenant (fixed by license/env or from session)."""
    try:
        if TENANT_FIXED:
            return TENANT_DEFAULT
    except Exception:
        pass
    try:
        from flask import session as _session
        return str(_session.get("tenant", "") or TENANT_DEFAULT)
    except Exception:
        return TENANT_DEFAULT


def suggest_existing_folder(base_path: str, tenant: str, kdnr: str, name: str) -> str:
    """Heuristic: find an existing customer folder for this tenant."""
    try:
        root = Path(base_path) / tenant
        if not root.exists():
            return ""
        k = (kdnr or "").strip()
        n = (name or "").strip().lower()
        candidates = []
        for p in root.glob("*"):
            if not p.is_dir():
                continue
            s = p.name.lower()
            if k and s.startswith(k.lower() + "_"):
                return str(p)
            if n and n in s:
                candidates.append(str(p))
        return candidates[0] if candidates else ""
    except Exception:
        return ""

TENANT_REQUIRE = (os.environ.get("KUKANILEA_TENANT_REQUIRE", "1").strip() == "1") and (not TENANT_FIXED)
TENANT_ALLOWLIST = [x.strip().lower() for x in os.environ.get("KUKANILEA_TENANTS", "").split(",") if x.strip()]

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


def _logged_in() -> bool:
    if rbac_verify_user is None:
        return True
    return bool(session.get("user"))


def _current_user() -> str:
    if rbac_verify_user is None:
        return "dev"
    return str(session.get("user") or "")


def _current_roles() -> List[str]:
    if rbac_verify_user is None:
        return ["DEV"]
    return list(session.get("roles") or [])


def _audit(action: str, target: str = "", meta: dict = None) -> None:
    if audit_log is None:
        return
    try:
        roles = _current_roles()
        role = roles[0] if roles else ""
        audit_log(user=_current_user(), role=role, action=action, target=target, meta=meta or {})
    except Exception:
        pass


def _ensure_bootstrap_admin() -> None:
    if not (rbac_verify_user and rbac_create_user and rbac_assign_role and rbac_get_user_roles):
        return
    if not (BOOTSTRAP_ADMIN_USER and BOOTSTRAP_ADMIN_PASS):
        return
    try:
        if rbac_verify_user(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS):
            return
        rbac_create_user(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS)
        rbac_assign_role(BOOTSTRAP_ADMIN_USER, "ADMIN")
        _audit("bootstrap_admin", target=BOOTSTRAP_ADMIN_USER, meta={})
    except Exception:
        pass


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


def _tenant_or_error(raw: str) -> Tuple[str, Optional[str]]:
    t = _norm_tenant(raw or "")
    if not t:
        t = _norm_tenant(TENANT_DEFAULT)
    if TENANT_REQUIRE and not t:
        return "", "tenant_missing"
    if TENANT_ALLOWLIST and t and t not in TENANT_ALLOWLIST:
        return "", "tenant_not_allowed"
    return t, None


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
    return render_template_string(
        HTML_BASE,
        content=content,
        ablage=str(BASE_PATH),
        user=_current_user() or "-",
        roles=", ".join(_current_roles()) or "-",
        active_tab=active_tab
    )


# -------- UI Templates ----------
HTML_BASE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KUKANILEA Systems</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  const savedTheme = localStorage.getItem("ks_theme") || "dark";
  const savedAccent = localStorage.getItem("ks_accent") || "indigo";
  if(savedTheme === "light"){ document.documentElement.classList.add("light"); }
  document.documentElement.dataset.accent = savedAccent;
</script>
<style>
  :root{ --accent-500:#6366f1; --accent-600:#4f46e5; }
  html[data-accent="indigo"]{ --accent-500:#6366f1; --accent-600:#4f46e5; }
  html[data-accent="emerald"]{ --accent-500:#10b981; --accent-600:#059669; }
  html[data-accent="amber"]{ --accent-500:#f59e0b; --accent-600:#d97706; }
  .btn-primary{ background:var(--accent-600); color:white; }
  .btn-primary:hover{ filter:brightness(1.05); }
  .btn-outline{ border:1px solid rgba(148,163,184,.35); }
  .light body { background:#f8fafc !important; color:#0f172a !important; }
  .light .card { background:rgba(255,255,255,.95) !important; border-color:#e2e8f0 !important; }
  .light .muted { color:#475569 !important; }
  .light .input { background:#ffffff !important; border-color:#cbd5e1 !important; color:#0f172a !important; }
  .light .btn-outline{ border-color:#cbd5e1 !important; }
  .accentText{ color:var(--accent-500); }
  .tab { border:1px solid rgba(148,163,184,.25); }
  .tab.active { border-color: rgba(148,163,184,.55); background: rgba(2,6,23,.35); }
  .light .tab.active { background:#ffffff !important; }
</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
<div class="max-w-[1600px] mx-auto p-4 md:p-6">
  <div class="flex items-start justify-between gap-3 mb-5">
    <div>
      <h1 class="text-3xl font-bold">KUKANILEA Systems</h1>
      <div class="muted text-sm">Upload → Review → Ablage • Tasks • Local Chat</div>
      <div class="muted text-xs mt-1">Ablage: {{ablage}}</div>
    </div>
    <div class="flex items-center gap-2">
      <div class="text-right">
        <div class="text-xs muted">Login</div>
        <div class="text-sm font-semibold">{{user}}</div>
        <div class="text-[11px] muted">{{roles}}</div>
      </div>
      {% if user and user != 'dev' %}
      <a class="rounded-xl px-3 py-2 text-sm card btn-outline" href="/logout">Logout</a>
      {% endif %}
      <button id="accentBtn" class="rounded-xl px-3 py-2 text-sm card btn-outline">Accent: <span id="accentLabel"></span></button>
      <button id="themeBtn" class="rounded-xl px-3 py-2 text-sm card btn-outline">Theme: <span id="themeLabel"></span></button>
    </div>
  </div>
  <div class="flex flex-wrap gap-2 mb-5">
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='upload' else ''}}" href="/">Upload/Queue</a>
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='tasks' else ''}}" href="/tasks">Tasks</a>
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='assistant' else ''}}" href="/assistant">Assistant</a>
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='chat' else ''}}" href="/chat">Local Chat</a>
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='mail' else ''}}" href="/mail">Mail Agent</a>
  </div>
  {{ content|safe }}
</div>

<!-- Floating Chat Widget -->
<div id="chatWidgetBtn" title="Chat" class="fixed bottom-5 right-5 z-50 cursor-pointer select-none rounded-full border bg-white/90 text-slate-900 shadow-lg backdrop-blur px-4 py-3 text-sm dark:bg-slate-900/90 dark:text-slate-100">
  💬
</div>

<div id="chatWidgetPanel" class="fixed bottom-20 right-5 z-50 hidden w-[380px] max-w-[92vw] overflow-hidden rounded-2xl border bg-white shadow-2xl dark:bg-slate-900">
  <div class="flex items-center justify-between border-b px-4 py-2 dark:border-slate-800">
    <div class="text-sm font-semibold">KUKANILEA Chat</div>
    <button id="chatWidgetClose" class="rounded-lg px-2 py-1 text-sm hover:bg-slate-100 dark:hover:bg-slate-800">✕</button>
  </div>
  <div class="px-4 py-2 border-b dark:border-slate-800">
    <div class="flex gap-2 items-center">
      <input id="chatWidgetKdnr" class="w-24 rounded-lg border px-2 py-1 text-sm dark:bg-slate-950 dark:border-slate-800" placeholder="KDNR" />
      <select id="chatWidgetMode" class="flex-1 rounded-lg border px-2 py-1 text-sm dark:bg-slate-950 dark:border-slate-800">
        <option value="ollama">ollama</option>
        <option value="search">search</option>
      </select>
      <button id="chatWidgetClear" class="rounded-lg border px-2 py-1 text-sm hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800">Clear</button>
    </div>
    <div id="chatWidgetStatus" class="mt-1 text-xs opacity-75">Tippe eine Frage…</div>
  </div>
  <div id="chatWidgetMsgs" class="h-[340px] overflow-auto px-3 py-3 space-y-2 text-sm"></div>
  <div class="border-t px-3 py-2 dark:border-slate-800">
    <div class="flex gap-2">
      <input id="chatWidgetInput" class="flex-1 rounded-xl border px-3 py-2 text-sm dark:bg-slate-950 dark:border-slate-800" placeholder="Nachrichten…" />
      <button id="chatWidgetSend" class="rounded-xl border px-3 py-2 text-sm hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800">Senden</button>
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

<!-- Floating Chat Widget -->
<button id="chatFab" class="fixed bottom-4 right-4 rounded-full shadow-lg px-4 py-3 text-sm card btn-primary z-50">
  💬 KI
</button>

<div id="chatModal" class="fixed inset-0 hidden z-50">
  <div class="absolute inset-0 bg-black/50" id="chatBackdrop"></div>
  <div class="absolute bottom-6 right-6 w-[92vw] max-w-md card rounded-2xl shadow-xl border overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b">
      <div class="font-semibold">KUKANILEA Chat</div>
      <button id="chatClose" class="btn-outline rounded-xl px-3 py-1 text-sm">✕</button>
    </div>
    <div class="p-3">
      <div class="text-xs opacity-70 mb-2">Frage etwas oder gib einen Auftrag: „Suche Rechnung von …“</div>
      <div id="chatMsgs" class="h-72 overflow-auto rounded-xl border p-2 text-sm space-y-2"></div>
      <div class="mt-3 flex gap-2">
        <input id="chatInput" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Nachricht…" />
        <button id="chatSend" class="rounded-xl px-4 py-2 text-sm card btn-primary">Senden</button>
      </div>
      <div class="mt-2 text-xs opacity-60" id="chatStatus"></div>
    </div>
  </div>
</div>

<script>
(function(){
  const fab=document.getElementById('chatFab');
  const modal=document.getElementById('chatModal');
  const backdrop=document.getElementById('chatBackdrop');
  const closeBtn=document.getElementById('chatClose');
  const msgs=document.getElementById('chatMsgs');
  const input=document.getElementById('chatInput');
  const sendBtn=document.getElementById('chatSend');
  const status=document.getElementById('chatStatus');

  function open(){ modal.classList.remove('hidden'); input.focus(); }
  function close(){ modal.classList.add('hidden'); }
  function add(role, text){
    const wrap=document.createElement('div');
    wrap.className = role==='user' ? 'flex justify-end' : 'flex justify-start';
    const bubble=document.createElement('div');
    bubble.className = role==='user'
      ? 'max-w-[85%] rounded-2xl px-3 py-2 bg-emerald-600 text-white'
      : 'max-w-[85%] rounded-2xl px-3 py-2 border';
    bubble.textContent = text;
    wrap.appendChild(bubble);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  async function send(){
    const q=input.value.trim();
    if(!q) return;
    input.value='';
    add('user', q);
    status.textContent='Denke…';
    try{
      const res = await fetch('/api/chat', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({q:q, mode:'ollama'})
      });
      if(!res.ok){
        const t = await res.text();
        status.textContent='Fehler: '+res.status;
        add('assistant', 'Fehler beim Chat ('+res.status+'). Bitte eingeloggt?');
        return;
      }
      const data = await res.json();
      add('assistant', data.answer || '(keine Antwort)');
      status.textContent='';
    }catch(e){
      status.textContent='Fehler';
      add('assistant', 'Verbindung fehlgeschlagen: '+e);
    }
  }

  fab && fab.addEventListener('click', open);
  backdrop && backdrop.addEventListener('click', close);
  closeBtn && closeBtn.addEventListener('click', close);
  sendBtn && sendBtn.addEventListener('click', send);
  input && input.addEventListener('keydown', (e)=>{ if(e.key==='Enter') send(); });

  // greet once per page load
  if(msgs && msgs.childElementCount===0){
    add('assistant', 'Hi! Wie kann ich helfen?');
  }
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
    <p class="text-sm opacity-80 mb-4">Dev-Account: <b>dev</b>/<b>dev</b> (Tenant: <b>KUKANILEA Dev</b>)</p>
    {% if error %}<div class="alert alert-error mb-3">{{ error }}</div>{% endif %}
    <form method="post" class="space-y-3">
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
      {% if tenant_fixed %}
      <div class="muted text-xs">Mandant (fix): <span class="font-semibold">{{tenant_fixed}}</span></div>
      <input type="hidden" id="tenant" name="tenant" value="{{tenant_fixed}}" />
      {% else %}
      <input id="tenant" name="tenant" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input"
        placeholder="Mandant/Firma (z.B. firma_x)" />
      {% endif %}
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
const tenantInput = document.getElementById("tenant");
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
  const res = await fetch("/api/progress/" + token, {cache:"no-store", credentials:"same-origin"});
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
  fd.append("tenant", (tenantInput?.value || "").trim());
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);
  xhr.upload.onprogress = (ev) => {
    if(ev.lengthComputable){ setProgress((ev.loaded / ev.total) * 35); phase.textContent = "Upload…"; }
  };
  xhr.onload = () => {
    if(xhr.status === 200){
      const resp = JSON.parse(xhr.responseText);
      status.textContent = "Upload OK. Analyse läuft…";
      poll(resp.token);
    } else {
      try{ const j = JSON.parse(xhr.responseText || "{}"); status.textContent = "Fehler beim Upload: " + (j.error || ("HTTP " + xhr.status)); }
      catch(e){ status.textContent = "Fehler beim Upload: HTTP " + xhr.status; }
    }
  };
  xhr.onerror = () => { status.textContent = "Upload fehlgeschlagen (Netzwerk/Server)."; };
  status.textContent = "Upload läuft…"; setProgress(0); phase.textContent = ""; xhr.send(fd);
});
</script>"""

HTML_REVIEW_SPLIT = r"""<div class="grid lg:grid-cols-2 gap-4">
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-4 card">
    <div class="flex items-center justify-between gap-2">
      <div>
        <div class="text-lg font-semibold">Preview</div>
        <div class="muted text-xs break-all">Token: {{token}} • Datei: {{filename}}</div>
      </div>
      <div class="flex items-center gap-2">
        <a class="text-sm underline accentText" href="/file/{{token}}" target="_blank">Datei öffnen</a>
        <a class="text-sm underline muted" href="/">Home</a>
      </div>
    </div>
    <div class="mt-3 rounded-xl border border-slate-800 overflow-hidden" style="height:72vh">
      {% if is_pdf %}
        <iframe src="/file/{{token}}" class="w-full h-full"></iframe>
      {% elif is_text %}
        <iframe src="/file/{{token}}" class="w-full h-full"></iframe>
      {% else %}
        <img src="/file/{{token}}" class="w-full h-full object-contain bg-black/20"/>
      {% endif %}
    </div>
    {% if preview %}
      <div class="mt-3">
        <div class="text-sm font-semibold mb-1">Preview (Auszug)</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-3 bg-slate-950/40 max-h-48 overflow-auto">{{preview}}</pre>
      </div>
    {% endif %}
  </div>
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-4 card">
    {{ right|safe }}
  </div>
</div>"""

HTML_WIZARD = r"""<form method="post" class="space-y-3" autocomplete="off">
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
      <label class="muted text-xs">Tenant/Mandant</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="tenant" value="{{w.tenant}}" placeholder="z.B. firma_x"/>
    </div>
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
      <div class="muted text-sm">Ollama lokal (kostenlos) oder Fallback via Dokument-Suche.</div>
    </div>
    <div class="muted text-xs">Mode: <span id="modeLbl"></span></div>
  </div>
  <div class="mt-4 flex flex-col md:flex-row gap-2">
    <select id="mode" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input md:w-56">
      <option value="ollama">ollama (http://127.0.0.1:11434)</option>
      <option value="fallback_assistant">fallback_assistant (Search+Snippets)</option>
    </select>
    <input id="kdnr" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input md:w-48" placeholder="Kdnr optional" />
    <input id="q" class="rounded-xl bg-slate-800 border border-slate-700 p-2 input flex-1" placeholder="Frag etwas… z.B. 'Was steht im Angebot 25-05475?'" />
    <button id="send" class="rounded-xl px-4 py-2 font-semibold btn-primary md:w-40">Senden</button>
  </div>
  <div class="mt-4 rounded-xl border border-slate-800 bg-slate-950/40 p-3" style="height:62vh; overflow:auto" id="log"></div>
  <div class="muted text-xs mt-3">
    Ollama Setup: <code>ollama pull llama3.1</code> • Dann neu laden.
  </div>
</div>
<script>
(function(){
  const log = document.getElementById("log");
  const q = document.getElementById("q");
  const kdnr = document.getElementById("kdnr");
  const mode = document.getElementById("mode");
  const modeLbl = document.getElementById("modeLbl");
  const send = document.getElementById("send");
  function add(role, text){
    const d = document.createElement("div");
    d.className = "mb-3";
    d.innerHTML = `<div class="muted text-[11px]">${role}</div><div class="text-sm whitespace-pre-wrap">${text}</div>`;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  function setModeLabel(){ modeLbl.textContent = mode.value; }
  setModeLabel();
  mode.addEventListener("change", setModeLabel);
  async function doSend(){
    const msg = (q.value || "").trim();
    if(!msg) return;
    add("you", msg);
    q.value = "";
    send.disabled = true;
    try{
      const res = await fetch("/api/chat", {method:"POST", credentials:"same-origin", credentials:"same-origin", headers: {"Content-Type":"application/json"}, body: JSON.stringify({mode: mode.value, q: msg, kdnr: (kdnr.value||"").trim()})});
      const j = await res.json();
      if(!res.ok){ add("system", "Fehler: " + (j.error || ("HTTP " + res.status))); }
      else { add("assistant", j.answer || "(leer)"); }
    }catch(e){ add("system", "Netzwerk/Server Fehler."); }
    finally{ send.disabled = false; }
  }
  send.addEventListener("click", doSend);
  q.addEventListener("keydown", (e)=>{ if(e.key==="Enter"){ e.preventDefault(); doSend(); }});

  // ---- Floating Chat Widget ----
  const _cw = {
    btn: document.getElementById('chatWidgetBtn'),
    panel: document.getElementById('chatWidgetPanel'),
    close: document.getElementById('chatWidgetClose'),
    msgs: document.getElementById('chatWidgetMsgs'),
    input: document.getElementById('chatWidgetInput'),
    send: document.getElementById('chatWidgetSend'),
    kdnr: document.getElementById('chatWidgetKdnr'),
    mode: document.getElementById('chatWidgetMode'),
    clear: document.getElementById('chatWidgetClear'),
    status: document.getElementById('chatWidgetStatus'),
  };
  function _cwAppend(role, text){
    if(!_cw.msgs) return;
    const wrap = document.createElement('div');
    const isUser = role === 'you';
    wrap.className = 'flex ' + (isUser ? 'justify-end' : 'justify-start');
    const bubble = document.createElement('div');
    bubble.className = (isUser
      ? 'max-w-[85%] rounded-2xl px-3 py-2 bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
      : 'max-w-[85%] rounded-2xl px-3 py-2 border bg-white dark:bg-slate-950 dark:border-slate-800');
    bubble.textContent = text;
    wrap.appendChild(bubble);
    _cw.msgs.appendChild(wrap);
    _cw.msgs.scrollTop = _cw.msgs.scrollHeight;
  }
  function _cwLoad(){
    try{
      const k = localStorage.getItem('kukanilea_cw_kdnr') || '';
      const m = localStorage.getItem('kukanilea_cw_mode') || 'ollama';
      if(_cw.kdnr) _cw.kdnr.value = k;
      if(_cw.mode) _cw.mode.value = m;
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
      if(_cw.mode) localStorage.setItem('kukanilea_cw_mode', _cw.mode.value || 'ollama');
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
  async function _cwSend(){
    const q = (_cw.input && _cw.input.value ? _cw.input.value.trim() : '');
    if(!q) return;
    _cwAppend('you', q);
    if(_cw.input) _cw.input.value = '';
    _cwSave();
    if(_cw.status) _cw.status.textContent = 'Denke…';
    try{
      const body = { q, kdnr: _cw.kdnr ? _cw.kdnr.value.trim() : '', mode: _cw.mode ? _cw.mode.value : 'ollama' };
      const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const j = await r.json();
      _cwAppend('assistant', j.answer || '(keine Antwort)');
      if(_cw.status) _cw.status.textContent = (j.mode ? ('Mode: ' + j.mode) : 'OK');
      _cwSave();
    }catch(e){
      _cwAppend('assistant', 'Fehler: ' + (e && e.message ? e.message : e));
      if(_cw.status) _cw.status.textContent = 'Fehler';
    }
  }
  if(_cw.btn && _cw.panel){
    _cw.btn.addEventListener('click', () => {
      _cw.panel.classList.toggle('hidden');
      _cwLoad();
      if(!_cw.panel.classList.contains('hidden') && _cw.input) _cw.input.focus();
    });
  }
  if(_cw.close) _cw.close.addEventListener('click', () => _cw.panel && _cw.panel.classList.add('hidden'));
  if(_cw.send) _cw.send.addEventListener('click', _cwSend);
  if(_cw.input) _cw.input.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ e.preventDefault(); _cwSend(); }});
  if(_cw.kdnr) _cw.kdnr.addEventListener('change', _cwSave);
  if(_cw.mode) _cw.mode.addEventListener('change', _cwSave);
  if(_cw.clear) _cw.clear.addEventListener('click', () => { if(_cw.msgs) _cw.msgs.innerHTML=''; localStorage.removeItem('kukanilea_cw_hist'); _cwSave(); });
  // ---- /Floating Chat Widget ----
})();
</script>"""

# -------- Routes / API ----------

# ============================================================
# Auth routes + global guard
# ============================================================
@APP.before_request
def _guard_login():
    # If RBAC is not enabled in core, allow everything (dev mode)
    if rbac_verify_user is None:
        return None
    # Allow these without login
    p = request.path or "/"
    if p.startswith("/static/") or p in ["/login", "/health"]:
        return None
    if not _logged_in():
        return redirect(url_for("login", next=p))
    return None


@APP.route("/login", methods=["GET", "POST"])
def login():
    if rbac_verify_user is None:
        # no RBAC → straight to home
        session["user"] = "dev"
        session["roles"] = ["DEV"]
        session["tenant"] = USER_TENANT.get("dev", "KUKANILEA Dev")
        return redirect(url_for("index"))

    _ensure_bootstrap_admin()
    error = ""
    nxt = request.args.get("next", "/")
    if request.method == "POST":
        u = (request.form.get("username") or "").strip().lower()
        pw = (request.form.get("password") or "").strip()
        if not u or not pw:
            error = "Bitte Username und Passwort eingeben."
        else:
            if rbac_verify_user(u, pw):
                session["user"] = u
                roles = rbac_get_user_roles(u) if rbac_get_user_roles else []
                session["roles"] = roles
                # tenant is fixed per company/license: enforce env/tenant-fixed or default
                session["tenant"] = _current_tenant() or _norm_tenant(TENANT_DEFAULT) or "default"
                _audit("login", target=u, meta={"roles": roles, "tenant": session.get("tenant")})
                return redirect(nxt or "/")
            error = "Login fehlgeschlagen."
    return _render_base(render_template_string(HTML_LOGIN, error=error), active_tab="upload")


@APP.route("/logout")
def logout():
    if rbac_verify_user is None:
        session.clear()
        return redirect(url_for("index"))
    if _logged_in():
        _audit("logout", target=_current_user(), meta={})
    session.clear()
    return redirect(url_for("login"))


@APP.route("/api/progress/<token>")
def api_progress(token: str):
    if (not _logged_in()) and (request.remote_addr not in ("127.0.0.1","::1")):
        return jsonify(error="unauthorized"), 401
    p = read_pending(token)
    if not p:
        return jsonify(error="not_found"), 404
    return jsonify(
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", "")
    )

@APP.route("/api/chat", methods=["POST"])
def _weather_answer(city: str) -> str:
    info = get_weather(city)
    if not info:
        return f"Ich konnte das Wetter für {city} nicht abrufen."
    # keep it short
    return f"Wetter {info.get('city','')}: {info.get('summary','')} (Temp: {info.get('temp_c','?')}°C, Wind: {info.get('wind_kmh','?')} km/h)"

def _tokenize_query(q: str):
    q = re.sub(r"[^0-9A-Za-zÄÖÜäöüß\- ]+", " ", q)
    parts = [p.strip() for p in q.split() if len(p.strip()) >= 2]
    # drop very common fillers
    stop = {"bitte","suche","find","datenbank","db","in","der","die","das","von","für","und","oder","mir","mal"}
    return [p for p in parts if p.lower() not in stop]

def _search_files(q: str, kdnr: str = ""):
    """
    Very lightweight filename/path search over Ablage + Pending.
    Returns list of {label, path, score}.
    """
    terms = _tokenize_query(q)
    if kdnr and kdnr not in terms:
        terms.append(kdnr)

    roots = []
    try:
        roots.append(Path(BASE_PATH))
    except Exception:
        pass
    try:
        roots.append(Path(PENDING_DIR))
    except Exception:
        pass

    hits = []
    exts = {".pdf",".png",".jpg",".jpeg",".txt",".md"}
    for root in roots:
        if not root or not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            hay = (str(p).lower())
            score = 0
            for t in terms:
                tl = t.lower()
                if tl and tl in hay:
                    score += 10
            # small boost for exact kdnr in path
            if kdnr and kdnr in hay:
                score += 15
            if score > 0:
                label = p.name
                hits.append({"label": label, "path": str(p), "score": score})
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits

def _ollama(q: str, kdnr: str = "") -> str:
    host = os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
    model = os.environ.get("KUKANILEA_OLLAMA_MODEL") or "llama3.1"
    prompt = (
        "Du bist KUKANILEA Systems, ein lokaler Betriebs-Assistent. "
        "Antworte auf Deutsch, klar und praxisnah. "
        "Wenn der User nach Dokumenten fragt, fordere Suchbegriffe/Kundennr an oder empfehle die Suche (Mode: search). "
    )
    if kdnr:
        prompt += f"Kontext: Kundennr={kdnr}. "
    prompt += f"\n\nUser: {q}\nAssistant:"

    try:
        url = host.rstrip("/") + "/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        txt = (out.get("response") or "").strip()
        return txt or "Keine Antwort vom Modell."
    except Exception as e:
        return f"Ollama nicht erreichbar oder Fehler: {e}. Tipp: Stelle sicher, dass 'ollama serve' läuft und OLLAMA_HOST stimmt."

def api_chat():
    """
    JSON in:
      { "q": "...", "kdnr": "1234" (optional), "mode": "ollama"|"search" (optional) }

    JSON out:
      { ok: true, answer: "...", mode: "...", hits: [...] (optional) }
    """
    _require_login()
    payload = request.get_json(silent=True) or {}
    q = (payload.get("q") or "").strip()
    kdnr = (payload.get("kdnr") or "").strip()
    mode = (payload.get("mode") or "ollama").strip().lower()
    if mode not in ("ollama", "search"):
        mode = "ollama"

    if not q:
        return jsonify(ok=False, answer="Leer.", mode=mode), 400

    ql = q.lower()

    # --- Tool: Weather (Berlin default) ---
    if any(w in ql for w in ("wetter", "temperatur", "regen", "sonne", "wind")):
        city = "Berlin"
        # crude city extraction: "... in <stadt>"
        m = re.search(r"\bin\s+([A-Za-zÄÖÜäöüß\- ]{2,40})\b", q, re.IGNORECASE)
        if m:
            city = m.group(1).strip()
        try:
            ans = _weather_answer(city)
            return jsonify(ok=True, answer=ans, mode="weather")
        except Exception as e:
            return jsonify(ok=True, answer=f"Wetter-Plugin Fehler: {e}", mode="weather")

    # --- Tool: Local search (DB/Ablage) ---
    # Always do search if explicitly requested or if mode=search
    wants_search = (mode == "search") or any(k in ql for k in ("suche", "find", "datenbank", "db", "rechnung", "angebot", "auftrag"))
    if wants_search:
        hits = _search_files(q=q, kdnr=kdnr)
        if not hits:
            return jsonify(
                ok=True,
                mode="search",
                answer="Keine Treffer in Ablage/Pending gefunden. Tipp: versuche 'suche <kundennr>' oder nutze genauer: Name + Datum + Dokumenttyp.",
                hits=[],
            )
        # Return a compact hit list and a short hint what user can do next.
        lines = []
        for h in hits[:10]:
            lines.append(f"- {h['label']} → {h['path']}")
        msg = "Ich habe diese Treffer gefunden:\n" + "\n".join(lines)
        msg += "\n\nSag z.B. 'öffne 1' oder 'zeige den Pfad von 3' oder verfeinere die Suche."
        return jsonify(ok=True, answer=msg, mode="search", hits=hits[:10])

    # --- Default: Ollama chat ---
    answer = _ollama(q, kdnr=kdnr)
    return jsonify(ok=True, answer=answer, mode="ollama")
# ==============================
# Ollama: best-effort autostart (dev convenience)
# ==============================
AUTO_START_OLLAMA = os.environ.get("KUKANILEA_AUTO_START_OLLAMA", "1").strip() not in ("0","false","False","no","NO")

_OLLAMA_PROC = None

def _ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip().rstrip("/")

def _ollama_model() -> str:
    return os.environ.get("KUKANILEA_OLLAMA_MODEL", "llama3.1").strip()

def _ollama_ok() -> bool:
    try:
        req = urllib.request.Request(_ollama_host() + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False

def _ensure_ollama():
    """Try to start 'ollama serve' if not running. Does not hard-fail."""
    global _OLLAMA_PROC
    if not AUTO_START_OLLAMA:
        return
    if _ollama_ok():
        return
    try:
        import subprocess, time
        _OLLAMA_PROC = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(12):
            time.sleep(0.4)
            if _ollama_ok():
                return
    except Exception:
        return

def _ollama_generate(prompt: str, system: str = "") -> str:
    """Raw generate helper for non-chat use (mail drafts, etc.)."""
    _ensure_ollama()
    if not _ollama_ok():
        raise RuntimeError("Ollama nicht erreichbar. Starte 'ollama serve' und prüfe OLLAMA_HOST.")
    payload = {
        "model": _ollama_model(),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    if system:
        payload["system"] = system
    req = urllib.request.Request(
        _ollama_host() + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
        return (data.get("response") or "").strip()


# ==============================
# Mail Agent Tab (Ollama + optional DeepL Write workflow)
# ==============================
HTML_MAIL = """
<div class="grid gap-4">
  <div class="card p-4 rounded-2xl border">
    <div class="text-lg font-semibold mb-1">Mail Agent</div>
    <div class="text-sm opacity-80 mb-4">Entwurf lokal mit Ollama. Danach optional in DeepL Write veredeln (ohne API: Copy/Paste).</div>

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
      <button id="m_deepl" class="rounded-xl px-4 py-2 text-sm btn-outline">DeepL Write öffnen</button>
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
  const deepl=document.getElementById('m_deepl');
  const status=document.getElementById('m_status');
  const out=document.getElementById('m_out');

  function v(id){ return (document.getElementById(id)?.value||'').trim(); }

  async function run(){
    status.textContent='Generiere…';
    out.value='';
    copy.disabled=true;
    try{
      const res = await fetch('/api/mail/draft', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
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
        status.textContent = 'Fehler: ' + (data.error || res.status);
        return;
      }
      out.value = data.text || '';
      copy.disabled = !out.value;
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

  function openDeepl(){
    window.open('https://www.deepl.com/write', '_blank');
  }

  gen && gen.addEventListener('click', run);
  copy && copy.addEventListener('click', doCopy);
  deepl && deepl.addEventListener('click', openDeepl);
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

@APP.get("/mail")
@login_required
def mail_page():
    _ensure_ollama()
    return _render_base(render_template_string(HTML_MAIL), active_tab="mail")

@APP.post("/api/mail/draft")
@login_required
def api_mail_draft():
    try:
        _ensure_ollama()
        payload = request.get_json(force=True) or {}
        to = (payload.get("to") or "").strip()
        subject = (payload.get("subject") or "").strip()
        tone = (payload.get("tone") or "neutral").strip()
        length = (payload.get("length") or "kurz").strip()
        context = (payload.get("context") or "").strip()

        if not context and not subject:
            return jsonify({"error": "Bitte Kontext oder Betreff angeben."}), 400

        text = _ollama_generate(_mail_prompt(to, subject, tone, length, context))
        return jsonify({"text": text, "meta": f"mode=ollama model={_ollama_model()}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@APP.route("/")
def index():
    items_meta = list_pending() or []
    items = [x.get("_token") for x in items_meta if x.get("_token")]
    meta = {}
    for it in items_meta:
        t = it.get("_token")
        if t:
            meta[t] = {"filename": it.get("filename",""), "progress": float(it.get("progress",0.0) or 0.0), "progress_phase": it.get("progress_phase","")}
    return _render_base(render_template_string(HTML_INDEX, items=items, meta=meta), active_tab="upload")

@APP.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="no_file"), 400
    tenant = (session.get("tenant") or _norm_tenant(TENANT_DEFAULT))
    # tenant is fixed by license/account; no user input here.
    filename = _safe_filename(f.filename)
    if not _is_allowed_ext(filename):
        return jsonify(error="unsupported"), 400
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

@APP.route("/review/<token>/delete", methods=["POST"])
def review_delete(token: str):
    try:
        delete_pending(token)
    except Exception:
        pass
    return redirect(url_for("index"))

@APP.route("/file/<token>")
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

@APP.route("/review/<token>/kdnr", methods=["GET","POST"])
def review(token: str):
    p = read_pending(token)
    if not p:
        return _render_base(_card("error", "Nicht gefunden."), active_tab="upload")
    if p.get("status") == "ANALYZING":
        right = _card("info", "Analyse läuft noch. Bitte kurz warten oder zurück zur Übersicht.")
        return _render_base(render_template_string(HTML_REVIEW_SPLIT, token=token, filename=p.get("filename",""), is_pdf=True, is_text=False, preview="", right=right), active_tab="upload")

    w = _wizard_get(p)
    if True:
        # Tenant is fixed per account/license
        w["tenant"] = (session.get("tenant") or p.get("tenant","") or _norm_tenant(TENANT_DEFAULT))

    suggested_doctype = (p.get("doctype_suggested") or "SONSTIGES").upper()
    if not w.get("doctype"):
        w["doctype"] = suggested_doctype if suggested_doctype in DOCTYPE_CHOICES else "SONSTIGES"
    suggested_date = (p.get("doc_date_suggested") or "").strip()

    # Suggest an existing customer folder (best effort)
    if not (w.get("existing_folder") or "").strip():
        w["existing_folder"] = suggest_existing_folder(BASE_PATH, w["tenant"], w.get("kdnr",""), w.get("name",""))

    msg = ""
    if request.method == "POST":
        if request.form.get("reextract") == "1":
            src = Path(p.get("path",""))
            if src.exists():
                try: delete_pending(token)
                except Exception: pass
                new_token = analyze_to_pending(src)
                return redirect(url_for("review", token=new_token))
            msg = "Quelle nicht gefunden – Re-Extract nicht möglich."

        if request.form.get("confirm") == "1":
            tenant = (session.get("tenant") or w.get("tenant") or _norm_tenant(TENANT_DEFAULT))
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
                            return redirect(url_for("done_view", token=token))
                        except Exception as e:
                            msg = f"Ablage fehlgeschlagen: {e}"

    _wizard_save(token, p, w)

    filename = p.get("filename","")
    ext = Path(filename).suffix.lower()
    is_pdf = ext == ".pdf"
    is_text = ext == ".txt"

    right = render_template_string(HTML_WIZARD, w=w, doctypes=DOCTYPE_CHOICES, suggested_doctype=suggested_doctype, suggested_date=suggested_date, extracted_text=p.get("extracted_text",""), msg=msg)
    return _render_base(render_template_string(HTML_REVIEW_SPLIT, token=token, filename=filename, is_pdf=is_pdf, is_text=is_text, preview=p.get("preview",""), right=right), active_tab="upload")

@APP.route("/done/<token>")
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

@APP.route("/assistant")
def assistant():
    # Ensure core searches within current tenant
    try:
        import kukanilea_core_v3_fixed as _core
        _core.TENANT_DEFAULT = _current_tenant() or _core.TENANT_DEFAULT
    except Exception:
        pass
    q = normalize_component(request.args.get("q","") or "")
    kdnr = normalize_component(request.args.get("kdnr","") or "")
    results = []
    if q and assistant_search is not None:
        try:
            raw = assistant_search(query=q, kdnr=kdnr, limit=50)
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

@APP.route("/tasks")
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

@APP.route("/chat")
def chat():
    return _render_base(HTML_CHAT, active_tab="chat")

@APP.route("/health")
def health():
    return jsonify(ok=True, ts=time.time(), app="kukanilea_upload_v3_ui")

if __name__ == "__main__":
    EINGANG.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    if db_init is not None:
        try: db_init()
        except Exception: pass
    _ensure_bootstrap_admin()
    print(f"http://127.0.0.1:{PORT}")
    APP.run(host="127.0.0.1", port=PORT, debug=True)
# Account → tenant mapping (tenant is NOT user-editable)
USER_TENANT = {
    "admin": "KUKANILEA Dev",
    "dev": "KUKANILEA Dev",
}
USER_ROLE = {
    "admin": "ADMIN",
    "dev": "DEV",
}

def ensure_dev_accounts():
    """Creates developer logins for local testing."""
    try:
        rbac_create_user("dev", "dev")
    except Exception:
        pass
    try:
        rbac_create_user("admin", "admin")
    except Exception:
        pass


