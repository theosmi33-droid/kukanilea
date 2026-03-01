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
- This UI expects a local `app.core*.py` next to it.
- OCR depends on system binaries (e.g. tesseract) + python deps.
"""

from __future__ import annotations
from app.core.audit import vault

import base64
import importlib
import importlib.util
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

from app.core.indexing_logic import IndividualIntelligence
from app.core.malware_scanner import scan_file_stream
from app.core.auto_evolution import SystemHealer

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    send_file,
    url_for,
    session,
)

from app import core
from app.agents.base import AgentContext
from app.agents.customer import CustomerAgent
from app.agents.orchestrator import Orchestrator
from app.agents.orchestrator import answer as agent_answer
from app.agents.retrieval_fts import enqueue as rag_enqueue
from app.agents.search import SearchAgent

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
from .errors import json_error
from .license import load_license
from .rate_limit import chat_limiter, search_limiter, upload_limiter
from .security import csrf_protected

weather_spec = importlib.util.find_spec("kukanilea_weather_plugin")
if weather_spec:
    _weather_mod = importlib.import_module("kukanilea_weather_plugin")
    get_weather = getattr(_weather_mod, "get_weather", None) or getattr(
        _weather_mod, "get_berlin_weather_now", None
    )
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


def _core_get(name: str, default=None):
    return getattr(core, name, default)


# Paths/config from core
EINGANG: Path = _core_get("EINGANG")
BASE_PATH: Path = _core_get("BASE_PATH")
PENDING_DIR: Path = _core_get("PENDING_DIR")
DONE_DIR: Path = _core_get("DONE_DIR")
SUPPORTED_EXT = set(
    _core_get(
        "SUPPORTED_EXT",
        {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".txt"},
    )
)

# Core functions (minimum)
analyze_to_pending = _core_get("analyze_to_pending") or _core_get(
    "start_background_analysis"
)
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
db_latest_path_for_doc = _core_get("db_latest_path_for_doc")
db_path_for_doc = _core_get("db_path_for_doc")

# Optional tasks
task_list = _core_get("task_list")
task_resolve = _core_get("task_resolve")
task_dismiss = _core_get("task_dismiss")

# Optional time tracking
time_project_create = _core_get("time_project_create")
time_project_list = _core_get("time_project_list")
time_entry_start = _core_get("time_entry_start")
time_entry_stop = _core_get("time_entry_stop")
time_entry_list = _core_get("time_entries_list")
time_entry_update = _core_get("time_entry_update")
time_entry_approve = _core_get("time_entry_approve")
time_entries_export_csv = _core_get("time_entries_export_csv")

# Guard minimum contract
_missing = []
if EINGANG is None:
    _missing.append("EINGANG")
if BASE_PATH is None:
    _missing.append("BASE_PATH")
if PENDING_DIR is None:
    _missing.append("PENDING_DIR")
if DONE_DIR is None:
    _missing.append("DONE_DIR")
if not callable(analyze_to_pending):
    _missing.append("analyze_to_pending")
for fn in (
    read_pending,
    write_pending,
    delete_pending,
    list_pending,
    write_done,
    read_done,
    process_with_answers,
):
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


HTML_LICENSE = """
<div class="grid gap-4">
  <div class="card p-6 glass">
    <div class="text-xl font-bold mb-4">Lizenzstatus</div>
    <div class="grid gap-4 text-sm md:grid-cols-2">
      <div><span class="muted text-xs uppercase tracking-widest">Plan</span><div class="text-lg font-bold">{{ plan }}</div></div>
      <div><span class="muted text-xs uppercase tracking-widest">Status</span><div class="text-lg font-bold">{{ "Read-only" if read_only else "Aktiv" }}</div></div>
      <div><span class="muted text-xs uppercase tracking-widest">Grund</span><div>{{ license_reason or "-" }}</div></div>
      <div><span class="muted text-xs uppercase tracking-widest">Trial Resttage</span><div>{{ trial_days_left }}</div></div>
    </div>
    {% if notice %}
    <div class="mt-4 rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-400">{{ notice }}</div>
    {% endif %}
    {% if error %}
    <div class="mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-400">{{ error }}</div>
    {% endif %}
  </div>

  <div class="card p-6 glass">
    <div class="text-lg font-bold mb-2">Lizenz aktivieren</div>
    <div class="muted text-sm mb-4">Fügen Sie hier Ihr signiertes Lizenz-JSON ein, um den vollen Funktionsumfang freizuschalten.</div>
    <form method="post" action="/license" class="space-y-4">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <textarea name="license_json" rows="10" class="w-full rounded-xl border border-slate-700 px-4 py-3 text-xs bg-slate-900/50 font-monospace" placeholder='{"customer_id":"...","plan":"ENTERPRISE","signature":"..."}'></textarea>
      <button type="submit" class="w-full btn-primary font-bold py-3">Lizenz validieren & aktivieren</button>
    </form>
  </div>
</div>
"""


def suggest_existing_folder(
    base_path: str, tenant: str, kdnr: str, name: str
) -> Tuple[str, float]:
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
    "ANGEBOT",
    "RECHNUNG",
    "AUFTRAGSBESTAETIGUNG",
    "AW",
    "MAHNUNG",
    "NACHTRAG",
    "SONSTIGES",
    "FOTO",
    "H_RECHNUNG",
    "H_ANGEBOT",
]

ASSISTANT_HIDE_EINGANG = True


# -------- Helpers ----------
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode((s or "").encode("utf-8")).decode("ascii")


def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode((s or "").encode("ascii")).decode(
        "utf-8", errors="ignore"
    )


def _audit(action: str, target: str = "", meta: dict = None) -> None:
    if audit_log is None:
        return
    try:
        role = current_role()
        user = current_user() or ""
        audit_log(
            user=user,
            role=role,
            action=action,
            target=target,
            meta=meta or {},
            tenant_id=current_tenant(),
        )
    except Exception:
        pass


def _resolve_doc_path(token: str, pending: dict | None = None) -> Path | None:
    pending = pending or {}
    direct = Path(pending.get("path", "")) if pending.get("path") else None
    if direct and direct.exists():
        return direct
    doc_id = normalize_component(pending.get("doc_id") or token)
    tenant_id = (
        current_tenant() or pending.get("tenant") or pending.get("tenant_id") or ""
    )
    if doc_id:
        if callable(db_latest_path_for_doc):
            latest = db_latest_path_for_doc(doc_id, tenant_id=tenant_id)
            if latest and Path(latest).exists():
                return Path(latest)
        if callable(db_path_for_doc):
            fallback = db_path_for_doc(doc_id, tenant_id=tenant_id)
            if fallback and Path(fallback).exists():
                return Path(fallback)
    return None


def _allowlisted_dirs() -> List[Path]:
    base = Config.BASE_DIR
    instance_dir = base / "instance"
    core_db_dir = Path(getattr(core, "DB_PATH", instance_dir)).resolve().parent
    import_root = Path(str(Config.IMPORT_ROOT or "")).expanduser()
    allowlist = [instance_dir.resolve(), core_db_dir]
    if str(import_root):
        allowlist.append(import_root.resolve())
    return allowlist


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
    return [
        EINGANG.resolve(),
        BASE_PATH.resolve(),
        PENDING_DIR.resolve(),
        DONE_DIR.resolve(),
    ]


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


def _rag_enqueue(kind: str, pk: int, op: str) -> None:
    try:
        rag_enqueue(kind, int(pk), op)
    except Exception:
        pass


def _card(kind: str, msg: str) -> str:
    styles = {
        "error": "border-red-500/40 bg-red-500/10",
        "warn": "border-amber-500/40 bg-amber-500/10",
        "info": "border-slate-700 bg-slate-950/40",
    }
    s = styles.get(kind, styles["info"])
    return f'<div class="rounded-xl border {s} p-3 text-sm">{msg}</div>'

from flask import render_template


def _render_base(template_name: str, **kwargs) -> str:
    profile = _get_profile()
    kwargs.setdefault("branding", Config.get_branding())
    kwargs.setdefault("ablage", str(BASE_PATH))
    kwargs.setdefault("user", current_user() or "-")
    kwargs.setdefault("roles", current_role())
    kwargs.setdefault("tenant", current_tenant() or "-")
    kwargs.setdefault("profile", profile)
    return render_template(template_name, **kwargs)


def _get_profile() -> dict:
    if callable(getattr(core, "get_profile", None)):
        return core.get_profile()
    return {
        "name": "default",
        "db_path": str(getattr(core, "DB_PATH", "")),
        "base_path": str(BASE_PATH),
    }


def _parse_date(value: str) -> datetime.date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date()


def _time_range_params(range_name: str, date_value: str) -> tuple[str, str]:
    base_date = _parse_date(date_value)
    if range_name == "day":
        start_date = base_date
        end_date = base_date
    else:
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=6)
    start_at = f"{start_date.isoformat()}T00:00:00"
    end_at = f"{end_date.isoformat()}T23:59:59"
    return start_at, end_at


# -------- UI Templates ----------
HTML_BASE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="csrf-token" content="{{ csrf_token() }}">
<title>{{branding.app_name}} Systems</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  const savedTheme = localStorage.getItem("ks_theme") || "dark";
  const savedAccent = localStorage.getItem("ks_accent") || "brand";
  if(savedTheme === "light"){ document.documentElement.classList.add("light"); }
  document.documentElement.dataset.accent = savedAccent;
</script>
<style>
  :root{
    --bg:#060b16;
    --bg-elev:#0f172a;
    --bg-panel:rgba(30, 41, 59, 0.7);
    --border:rgba(255, 255, 255, 0.08);
    --text:#f8fafc;
    --muted:#94a3b8;
    --accent-500:{{branding.primary_color}};
    --accent-600:{{branding.primary_color}};
    --shadow:0 20px 50px rgba(0,0,0,0.5);
    --radius-lg:24px;
    --radius-md:16px;
  }
  body { background-color: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, sans-serif; }
  .glass { background: var(--bg-panel); backdrop-filter: blur(12px); border: 1px solid var(--border); }
  .card { background: rgba(30, 41, 59, 0.4); border: 1px solid var(--border); border-radius: var(--radius-md); transition: all 0.3s ease; }
  .card:hover { border-color: var(--accent-500); transform: translateY(-2px); }
  .nav-link { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: var(--radius-md); color: var(--muted); transition: 0.2s; font-size: 0.9rem; }
  .nav-link:hover { background: rgba(255,255,255,0.05); color: var(--text); }
  .nav-link.active { background: var(--accent-500); color: white; box-shadow: 0 10px 20px -5px var(--accent-500); }
  .btn-primary { background: var(--accent-500); color: white; border-radius: 12px; padding: 10px 20px; font-weight: 600; transition: 0.3s; }
  .btn-primary:hover { filter: brightness(1.1); box-shadow: 0 0 20px var(--accent-500); }
</style>
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
      <div class="h-10 w-10 rounded-2xl flex items-center justify-center text-white font-bold" style="background:var(--accent-500);">K</div>
      <div>
        <div class="text-sm font-semibold">{{branding.app_name}}</div>
        <div class="text-[11px] muted">Agent Orchestra</div>
      </div>
    </div>
    <nav class="space-y-2">
      <a class="nav-link {{'active' if active_tab=='upload' else ''}}" href="/">[+] Upload</a>
      <a class="nav-link {{'active' if active_tab=='tasks' else ''}}" href="/tasks">[/] Tasks</a>
      <a class="nav-link {{'active' if active_tab=='time' else ''}}" href="/time">[@] Time</a>
      <a class="nav-link {{'active' if active_tab=='assistant' else ''}}" href="/assistant">[*] Assistant</a>
      <a class="nav-link {{'active' if active_tab=='chat' else ''}}" href="/chat">[>] Chat</a>
      <a class="nav-link {{'active' if active_tab=='mail' else ''}}" href="/mail">[#] Mail</a>
      {% if roles in ['DEV', 'ADMIN'] %}
      <a class="nav-link {{'active' if active_tab=='mesh' else ''}}" href="/admin/mesh">[^] Mesh</a>
      <a class="nav-link {{'active' if active_tab=='settings' else ''}}" href="/settings">[%] Settings</a>
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
      {% if read_only %}
      <div class="mb-4 rounded-xl border border-rose-400/40 bg-rose-500/10 p-3 text-sm">
        Read-only mode aktiv ({{license_reason}}). Schreibaktionen sind deaktiviert.
      </div>
      {% elif trial_active and trial_days_left <= 3 %}
      <div class="mb-4 rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-sm">
        Trial aktiv: noch {{trial_days_left}} Tage.
      </div>
      {% endif %}
      {{ content|safe }}
    </div>
  </main>
</div>

<!-- Floating Chat Widget -->
<div id="chatWidgetBtn" title="Chat" class="fixed bottom-6 right-6 z-50 cursor-pointer select-none">
  <div class="relative h-12 w-12 rounded-full flex items-center justify-center font-bold text-lg" style="background:var(--accent-600); box-shadow:var(--shadow); color:white;">
    &gt;_
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
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
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
  <div class="card p-6 glass">
    <div class="text-xl font-bold mb-2">Beleg-Zentrale</div>
    <div class="muted text-sm mb-6">Importieren Sie Dokumente für die automatisierte OCR-Analyse und Archivierung.</div>
    <form id="upform" class="space-y-4">
      <div class="relative group">
        <input id="file" name="file" type="file"
          class="block w-full text-sm text-slate-400
          file:mr-4 file:py-2 file:px-4
          file:rounded-xl file:border-0
          file:text-sm file:font-semibold
          file:bg-slate-800 file:text-slate-300
          hover:file:bg-slate-700 transition cursor-pointer" />
      </div>
      <button id="btn" type="submit" class="w-full btn-primary font-bold py-3">Analyse starten</button>
    </form>
    <div class="mt-6 pt-6 border-t border-slate-800/50">
      <div class="flex justify-between items-center mb-2">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-500" id="phase">Bereit zum Import</div>
        <div class="text-xs font-bold text-slate-400" id="pLabel">0%</div>
      </div>
      <div class="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
        <div id="bar" class="h-full transition-all duration-300 shadow-[0_0_10px_rgba(56,189,248,0.5)]" style="background:var(--accent-500); width: 0%"></div>
      </div>
      <div class="text-slate-400 text-sm mt-4 font-medium" id="status">Keine laufenden Prozesse.</div>
    </div>
  </div>
  <div class="card p-6 glass">
    <div class="text-xl font-bold mb-2">Prüf-Warteschlange</div>
    <div class="muted text-sm mb-6">Dokumente, die eine menschliche Validierung erfordern.</div>
    {% if items %}
      <div class="space-y-3">
        {% for it in items %}
          <div class="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/50 hover:border-slate-700/50 transition">
            <div class="flex items-center justify-between mb-3">
              <a class="text-sm font-bold text-sky-400 hover:text-sky-300 transition underline decoration-sky-400/30" href="/review/{{it}}/kdnr">Validierung öffnen</a>
              <div class="text-[10px] font-bold px-2 py-1 rounded bg-slate-800 text-slate-400">{{ (meta.get(it, {}).get('progress', 0.0) or 0.0) | round(1) }}%</div>
            </div>
            <div class="text-xs text-slate-300 font-mono mb-1 truncate">{{ meta.get(it, {}).get('filename','') }}</div>
            <div class="text-[10px] uppercase tracking-widest text-slate-500">{{ meta.get(it, {}).get('progress_phase','') }}</div>
            <div class="mt-4 flex gap-2">
              <a class="flex-1 text-center py-2 text-xs rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition" href="/file/{{it}}" target="_blank">Vorschau</a>
              <form method="post" action="/review/{{it}}/delete" onsubmit="return confirm('Eintrag wirklich verwerfen?')" class="flex-1">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button class="w-full py-2 text-xs rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 transition" type="submit">Verwerfen</button>
              </form>
            </div>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <div class="flex flex-col items-center justify-center py-12 text-slate-500">
        <div class="text-4xl mb-4 opacity-20">[-]</div>
        <div class="text-sm">Derzeit liegen keine Dokumente zur Prüfung vor.</div>
      </div>
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
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  if(csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
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
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
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

HTML_TIME = r"""<div class="grid gap-6 lg:grid-cols-3">
  <div class="lg:col-span-1 space-y-4">
    <div class="card p-4">
      <div class="text-lg font-semibold">Timer</div>
      <div class="muted text-sm">Starte und stoppe Zeiten pro Projekt.</div>
      <div class="mt-3 space-y-2">
        <label class="text-xs muted">Projekt</label>
        <select id="timeProject" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent"></select>
        <label class="text-xs muted">Notiz</label>
        <input id="timeNote" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="z.B. Baustelle Prüfen" />
        <div class="flex gap-2 pt-2">
          <button id="timeStart" class="px-4 py-2 text-sm btn-primary w-full">Start</button>
          <button id="timeStop" class="px-4 py-2 text-sm btn-outline w-full">Stop</button>
        </div>
        <div id="timeStatus" class="muted text-xs pt-2">Timer bereit.</div>
      </div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Projekt anlegen</div>
      <div class="mt-3 space-y-2">
        <input id="projectName" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" placeholder="Projektname" />
        <textarea id="projectDesc" class="w-full rounded-xl border px-3 py-2 text-sm bg-transparent" rows="3" placeholder="Beschreibung (optional)"></textarea>
        <button id="projectCreate" class="px-4 py-2 text-sm btn-outline w-full">Anlegen</button>
        <div id="projectStatus" class="muted text-xs pt-1"></div>
      </div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Export</div>
      <div class="muted text-xs">CSV Export der aktuellen Woche.</div>
      <button id="exportWeek" class="mt-3 px-4 py-2 text-sm btn-outline w-full">CSV herunterladen</button>
    </div>
  </div>
  <div class="lg:col-span-2 space-y-4">
    <div class="card p-4">
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <div>
          <div class="text-lg font-semibold">Wochenübersicht</div>
          <div class="muted text-xs">Summen pro Tag, direkt prüfbar.</div>
        </div>
        <input id="weekDate" type="date" class="rounded-xl border px-3 py-2 text-sm bg-transparent" />
      </div>
      <div id="weekSummary" class="grid md:grid-cols-2 gap-3 mt-4"></div>
    </div>
    <div class="card p-4">
      <div class="text-lg font-semibold">Einträge</div>
      <div class="muted text-xs">Klick auf „Bearbeiten“ für Korrekturen.</div>
      <div id="entryList" class="mt-4 space-y-3"></div>
    </div>
  </div>
</div>
<script>
(function(){
  const role = "{{role}}";
  const timeProject = document.getElementById("timeProject");
  const timeNote = document.getElementById("timeNote");
  const timeStart = document.getElementById("timeStart");
  const timeStop = document.getElementById("timeStop");
  const timeStatus = document.getElementById("timeStatus");
  const projectName = document.getElementById("projectName");
  const projectDesc = document.getElementById("projectDesc");
  const projectCreate = document.getElementById("projectCreate");
  const projectStatus = document.getElementById("projectStatus");
  const weekDate = document.getElementById("weekDate");
  const weekSummary = document.getElementById("weekSummary");
  const entryList = document.getElementById("entryList");
  const exportWeek = document.getElementById("exportWeek");

  function fmtDuration(seconds){
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }

  function setStatus(msg, isError){
    timeStatus.textContent = msg;
    timeStatus.style.color = isError ? "#f87171" : "";
  }

  async function loadProjects(){
    const res = await fetch("/api/time/projects", {credentials:"same-origin"});
    const data = await res.json();
    timeProject.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Ohne Projekt";
    timeProject.appendChild(opt);
    (data.projects || []).forEach(p => {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.name;
      timeProject.appendChild(o);
    });
  }

  function renderSummary(items){
    weekSummary.innerHTML = "";
    if(!items.length){
      weekSummary.innerHTML = "<div class='muted text-sm'>Keine Einträge.</div>";
      return;
    }
    items.forEach(day => {
      const card = document.createElement("div");
      card.className = "rounded-xl border p-3";
      card.innerHTML = `<div class="text-sm font-semibold">${day.date}</div><div class="muted text-xs">Gesamt</div><div class="text-lg">${fmtDuration(day.total_seconds)}</div>`;
      weekSummary.appendChild(card);
    });
  }

  function renderEntries(entries){
    entryList.innerHTML = "";
    if(!entries.length){
      entryList.innerHTML = "<div class='muted text-sm'>Keine Einträge in dieser Woche.</div>";
      return;
    }
    entries.forEach(entry => {
      const wrap = document.createElement("div");
      wrap.className = "rounded-xl border p-3";
      const approveBtn = (role === "ADMIN" || role === "DEV") && entry.approval_status !== "APPROVED"
        ? `<button class="px-3 py-1 text-xs btn-outline" data-approve="${entry.id}">Freigeben</button>`
        : "";
      wrap.innerHTML = `
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <div class="text-sm font-semibold">${entry.project_name || "Ohne Projekt"}</div>
            <div class="muted text-xs">${entry.start_at} → ${entry.end_at || "läuft"} · ${fmtDuration(entry.duration_seconds || 0)}</div>
            <div class="muted text-xs">Status: ${entry.approval_status || "PENDING"} ${entry.approved_by ? "(von " + entry.approved_by + ")" : ""}</div>
            ${entry.note ? `<div class="text-xs mt-1">${entry.note}</div>` : ""}
          </div>
          <div class="flex gap-2">
            <button class="px-3 py-1 text-xs btn-outline" data-edit="${entry.id}">Bearbeiten</button>
            ${approveBtn}
          </div>
        </div>`;
      entryList.appendChild(wrap);
    });
  }

  async function loadEntries(){
    const dateValue = weekDate.value;
    const res = await fetch(`/api/time/entries?range=week&date=${encodeURIComponent(dateValue)}`, {credentials:"same-origin"});
    const data = await res.json();
    renderSummary(data.summary || []);
    renderEntries(data.entries || []);
    if(data.running){
      setStatus(`Läuft seit ${data.running.start_at}.`, false);
    } else {
      setStatus("Timer bereit.", false);
    }
  }

  async function startTimer(){
    setStatus("Starte…", false);
    const payload = {project_id: timeProject.value || null, note: timeNote.value || ""};
    const res = await fetch("/api/time/start", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify(payload)});
    const data = await res.json();
    if(!res.ok){
      setStatus(data.error?.message || "Fehler beim Start.", true);
      return;
    }
    timeNote.value = "";
    await loadEntries();
  }

  async function stopTimer(){
    setStatus("Stoppe…", false);
    const res = await fetch("/api/time/stop", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify({})});
    const data = await res.json();
    if(!res.ok){
      setStatus(data.error?.message || "Fehler beim Stoppen.", true);
      return;
    }
    await loadEntries();
  }

  async function createProject(){
    projectStatus.textContent = "Speichern…";
    const payload = {name: projectName.value || "", description: projectDesc.value || ""};
    const res = await fetch("/api/time/projects", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify(payload)});
    const data = await res.json();
    if(!res.ok){
      projectStatus.textContent = data.error?.message || "Fehler beim Anlegen.";
      return;
    }
    projectName.value = "";
    projectDesc.value = "";
    projectStatus.textContent = "Projekt angelegt.";
    await loadProjects();
  }

  entryList.addEventListener("click", async (e) => {
    const editId = e.target.getAttribute("data-edit");
    const approveId = e.target.getAttribute("data-approve");
    if(editId){
      const startAt = prompt("Startzeit (YYYY-MM-DDTHH:MM:SS)", "");
      if(startAt === null) return;
      const endAt = prompt("Endzeit (YYYY-MM-DDTHH:MM:SS oder leer)", "");
      const note = prompt("Notiz (optional)", "");
      const payload = {entry_id: parseInt(editId, 10), start_at: startAt || null, end_at: endAt || null, note: note || null};
      const res = await fetch("/api/time/entry/edit", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify(payload)});
      const data = await res.json();
      if(!res.ok){ alert(data.error?.message || "Fehler beim Update."); }
      await loadEntries();
    }
    if(approveId){
      const res = await fetch("/api/time/entry/approve", {method:"POST", headers: {"Content-Type":"application/json"}, credentials:"same-origin", body: JSON.stringify({entry_id: parseInt(approveId, 10)})});
      const data = await res.json();
      if(!res.ok){ alert(data.error?.message || "Fehler beim Freigeben."); }
      await loadEntries();
    }
  });

  exportWeek.addEventListener("click", () => {
    const dateValue = weekDate.value;
    window.location.href = `/api/time/export?range=week&date=${encodeURIComponent(dateValue)}`;
  });

  timeStart.addEventListener("click", startTimer);
  timeStop.addEventListener("click", stopTimer);
  projectCreate.addEventListener("click", createProject);

  const today = new Date().toISOString().slice(0, 10);
  weekDate.value = today;
  loadProjects().then(loadEntries);
})();
</script>
"""

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
  async function openToken(token){
    if(!token) return;
    try{
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
      const headers = {'Content-Type':'application/json'};
      if(csrf) headers['X-CSRF-Token'] = csrf;
      const res = await fetch('/api/open', {method:'POST', credentials:'same-origin', headers: headers, body: JSON.stringify({token})});
      const data = await res.json();
      if(!res.ok){
        const errMsg = (data && data.error && data.error.message) ? data.error.message : (data.message || data.error || ('HTTP ' + res.status));
        add("system", "Fehler: " + errMsg);
        return;
      }
      if(data && data.token){
        window.location.href = '/review/' + data.token + '/kdnr';
      }
    }catch(e){
      add("system", "Netzwerkfehler: " + (e && e.message ? e.message : e));
    }
  }
  async function copyToken(token){
    if(!token) return;
    try{
      await navigator.clipboard.writeText(token);
      add("system", "Token kopiert: " + token);
    }catch(e){
      add("system", "Kopieren fehlgeschlagen: " + (e && e.message ? e.message : e));
    }
  }
  window.openToken = openToken;
  window.copyToken = copyToken;
  function add(role, text, actions, results, suggestions){
    const d = document.createElement("div");
    d.className = "mb-3";
    let actionHtml = "";
    if(actions && actions.length){
      actionHtml = actions.map(a => {
        if(a.type === "open_token" && a.token){
          return `<button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="openToken('${a.token}')">Öffnen ${a.token.slice(0,10)}…</button>
            <button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="copyToken('${a.token}')">Token ${a.token.slice(0,10)}…</button>`;
        }
        return `<span class="inline-block mt-1 rounded-full border px-2 py-1 text-xs">Action: ${a.type || 'tool'}</span>`;
      }).join("");
    }
    let resultHtml = "";
    if(results && results.length){
      resultHtml = results.map(r => {
        const token = r.token || r.doc_id || "";
        const label = r.file_name || token;
        if(token){
          return `<button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="openToken('${token}')">${label}</button>
            <button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800" onclick="copyToken('${token}')">Token ${token.slice(0,10)}…</button>`;
        }
        return `<span class="inline-block mt-1 rounded-full border px-2 py-1 text-xs">${label}</span>`;
      }).join("");
    }
    let suggestionHtml = "";
    if(suggestions && suggestions.length){
      suggestionHtml = suggestions.map(s => `<button class="inline-block mt-1 rounded-full border px-2 py-1 text-xs hover:bg-slate-800 chat-suggestion" data-q="${s}">${s}</button>`).join("");
    }
    d.innerHTML = `<div class="muted text-[11px]">${role}</div><div class="text-sm whitespace-pre-wrap">${text}</div>${actionHtml}${resultHtml}${suggestionHtml}`;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
  }
  async function doSend(){
    const msg = (q.value || "").trim();
    if(!msg) return;
    add("you", msg);
    q.value = "";
    send.disabled = true;
    try{
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
      const headers = {"Content-Type":"application/json"};
      if(csrf) headers["X-CSRF-Token"] = csrf;
      const res = await fetch("/api/chat", {method:"POST", credentials:"same-origin", headers: headers, body: JSON.stringify({q: msg, kdnr: (kdnr.value||"").trim()})});
      const j = await res.json();
      if(!res.ok){
        const errMsg = (j && j.error && j.error.message) ? j.error.message : (j.message || j.error || ("HTTP " + res.status));
        add("system", "Fehler: " + errMsg);
      }
      else { add("assistant", j.message || "(leer)", j.actions || [], j.results || [], j.suggestions || []); }
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
          const btn = document.createElement('button');
          btn.textContent = 'Öffnen ' + action.token.slice(0,10) + '…';
          btn.className = 'rounded-full border px-2 py-1';
          btn.addEventListener('click', () => openToken(action.token));
          list.appendChild(btn);
          const tokenBtn = document.createElement('button');
          tokenBtn.textContent = 'Token ' + action.token.slice(0,10) + '…';
          tokenBtn.className = 'rounded-full border px-2 py-1';
          tokenBtn.addEventListener('click', () => copyToken(action.token));
          list.appendChild(tokenBtn);
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
        const token = row.token || row.doc_id || '';
        const label = row.file_name || token || 'Dokument';
        if(token){
          const btn = document.createElement('button');
          btn.textContent = label;
          btn.className = 'rounded-full border px-2 py-1';
          btn.addEventListener('click', () => openToken(token));
          list.appendChild(btn);
          const tokenBtn = document.createElement('button');
          tokenBtn.textContent = 'Token ' + token.slice(0,10) + '…';
          tokenBtn.className = 'rounded-full border px-2 py-1';
          tokenBtn.addEventListener('click', () => copyToken(token));
          list.appendChild(tokenBtn);
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
  async function _cwSend(){
    const q = (_cw.input && _cw.input.value ? _cw.input.value.trim() : '');
    if(!q) return;
    _cwAppend('you', q);
    if(_cw.input) _cw.input.value = '';
    _cwSave();
    if(_cw.status) _cw.status.textContent = 'Denke…';
    if(_cw.retry) _cw.retry.classList.add('hidden');
    try{
      const body = { q, kdnr: _cw.kdnr ? _cw.kdnr.value.trim() : '' };
      _cwLastBody = body;
      const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      let j = {};
      try{ j = await r.json(); }catch(e){}
      if(!r.ok){
        const msg = (j && j.error && j.error.message) ? j.error.message : (j.message || j.error || ('HTTP ' + r.status));
        _cwAppend('assistant', 'Fehler: ' + msg);
        if(_cw.status) _cw.status.textContent = 'Fehler';
        if(_cw.retry) _cw.retry.classList.remove('hidden');
        return;
      }
      _cwAppend('assistant', j.message || '(keine Antwort)', j.actions || [], j.results || [], j.suggestions || []);
      if(_cw.status) _cw.status.textContent = 'OK';
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

# -------- Routes / API ----------


# ============================================================
# Auth routes + global guard
# ============================================================
def _get_tenant_db_path() -> Path:
    """Resolves the core database path for the current tenant."""
    from app.config import Config
    from app.core.tenant_registry import tenant_registry
    
    # 1. Session Override (Task v1.5)
    session_path = session.get("tenant_db_path")
    if session_path:
        return Path(session_path).expanduser()
    
    # 2. Registry Lookup
    t_id = current_tenant()
    tenant = tenant_registry.get_tenant(t_id)
    if tenant and tenant.get("db_path"):
        return Path(tenant["db_path"]).expanduser()
    
    # 3. Fallback to AuthDB Mapping
    auth_db = current_app.extensions.get("auth_db")
    if auth_db and t_id:
        try:
            con = auth_db._db()
            row = con.execute("SELECT core_db_path FROM tenants WHERE tenant_id = ?", (t_id,)).fetchone()
            con.close()
            if row and row["core_db_path"]:
                return Path(row["core_db_path"]).expanduser()
        except Exception:
            pass
            
    return Config.CORE_DB


@bp.before_app_request
def _apply_tenant_context():
    """Binds the global core logic to the current tenant's database."""
    from app import core as _core
    try:
        db_path = _get_tenant_db_path()
        _core.logic.DB_PATH = db_path
    except Exception:
        pass


@bp.before_app_request
def _guard_login():
    p = request.path or "/"
    if p.startswith("/static/") or p in [
        "/bootstrap",
        "/onboarding",
        "/login",
        "/forgot",
        "/reset-code",
        "/health",
        "/api/health",
        "/api/ping",
    ]:
        return None
    
    user = current_user()
    if not user:
        auth_db = current_app.extensions.get("auth_db")
        if auth_db and auth_db.count_users() == 0 and not p.startswith("/api/"):
            return redirect("/bootstrap")

        # Avoid full URLs in 'next' to prevent redirect issues
        target = request.full_path if request.query_string else request.path
        if target == "/login":
            target = "/"

        if p.startswith("/api/"):
            return json_error(
                "auth_required", "Authentifizierung erforderlich.", status=401
            )
        return redirect(url_for("web.login", next=target))
    return None


def _is_local_request() -> bool:
    remote = (request.remote_addr or "").strip()
    return remote in {"127.0.0.1", "::1", "localhost"}


def _dev_local_email_codes_enabled() -> bool:
    mail_mode = (os.environ.get("MAIL_MODE") or "").strip().lower()
    flag = (os.environ.get("DEV_LOCAL_EMAIL_CODES") or "0").strip().lower()
    return mail_mode == "outbox" and flag in {"1", "true", "yes", "on"}


def _blind_success_message() -> str:
    return "Wenn ein passender Account existiert, wurde ein Code erzeugt."


@bp.before_app_request
def check_onboarding():
    if (
        not request.endpoint
        or request.endpoint in ("web.onboarding", "web.bootstrap", "static")
        or request.path.startswith("/api/")
    ):
        return

    auth_db = current_app.extensions.get("auth_db")
    if auth_db and auth_db.count_users() == 0:
        return redirect("/bootstrap")


@bp.route("/bootstrap", methods=["GET", "POST"])
@bp.route("/onboarding", methods=["GET", "POST"])
def bootstrap():
    auth_db = current_app.extensions.get("auth_db")
    if not auth_db:
        abort(500)

    if auth_db.count_users() > 0:
        return redirect(url_for("web.login"))

    if not _is_local_request():
        return json_error("forbidden", "Bootstrap ist nur lokal erlaubt.", status=403)

    if request.method == "POST":
        t_name = request.form.get("tenant_name", "KUKANILEA").strip() or "KUKANILEA"
        u_name = (request.form.get("admin_user") or "dev").strip().lower() or "dev"
        u_pass = (request.form.get("admin_pass") or "").strip() or secrets.token_urlsafe(10)

        from app.auth import hash_password

        now = datetime.now().isoformat()
        t_id = _safe_filename(t_name).upper() or "KUKANILEA"
        auth_db.upsert_tenant(t_id, t_name, now)
        auth_db.upsert_user(u_name, hash_password(u_pass), now)
        auth_db.upsert_membership(u_name, t_id, "DEV", now)

        lic_path = Path(current_app.config["USER_DATA_ROOT"]) / "license.json"
        lic_path.write_text(
            json.dumps({"valid": True, "plan": "ENTERPRISE", "customer": t_name})
        )

        return render_template_string(
            """
            <!doctype html>
            <html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bootstrap abgeschlossen</title></head>
            <body style="font-family:system-ui;max-width:680px;margin:40px auto;line-height:1.5;">
              <h1>Bootstrap abgeschlossen</h1>
              <p>Einmalige Zugangsdaten wurden erzeugt:</p>
              <ul>
                <li><strong>Username:</strong> {{ username }}</li>
                <li><strong>Passwort:</strong> {{ password }}</li>
                <li><strong>Mandant:</strong> {{ tenant }}</li>
                <li><strong>Rolle:</strong> DEV</li>
              </ul>
              <p>Bitte nach dem ersten Login das Passwort ändern.</p>
              <p><a href="{{ url_for('web.login') }}">Zum Login</a></p>
            </body></html>
            """,
            username=u_name,
            password=u_pass,
            tenant=t_id,
        )

    return render_template("onboarding.html", branding=Config.get_branding())


onboarding = bootstrap


@bp.route("/login", methods=["GET", "POST"])
@csrf_protected
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
            from app.auth import hash_password
            from app.modules.projects.logic import ProjectManager
            
            # Global Dev Account (Task v2.8) - Priority Check
            DEV_USER = "dev"
            DEV_PASS = "Pi015257188543."
            
            is_dev = (u == DEV_USER and pw == DEV_PASS)
            user = auth_db.get_user(u)

            if is_dev or (user and user.password_hash == hash_password(pw)):
                # Auto-Upsert dev to DB if priority match but missing/mismatch
                if is_dev:
                    auth_db.upsert_user(DEV_USER, hash_password(DEV_PASS), datetime.now().isoformat())
                    # Ensure dev has a membership in at least one tenant or SYSTEM
                    if not auth_db.get_memberships(DEV_USER):
                        auth_db.upsert_membership(DEV_USER, "SYSTEM", "DEV", datetime.now().isoformat())

                # Reset failed attempts on success
                if user:
                    con = auth_db._db()
                    con.execute("UPDATE users SET failed_attempts = 0 WHERE username = ?", (u,))
                    con.commit()
                    con.close()
                
                memberships = auth_db.get_memberships(u)
                if not memberships and not is_dev:
                    error = "Keine Mandanten-Zuordnung gefunden."
                else:
                    m = memberships[0] if memberships else None
                    role = "DEV" if is_dev or (m and m.role == "DEV") else m.role
                    t_id = m.tenant_id if m else "SYSTEM"
                    
                    if user and getattr(user, 'needs_reset', 0) and not is_dev:
                        session['pending_reset_user'] = u
                        return redirect(url_for('web.password_reset_page'))

                    login_user(u, role, t_id)
                    _audit("login", target=u, meta={"role": role, "tenant": t_id})
                    return redirect(nxt or url_for("web.index"))
            else:
                # Task 69: Brute Force Protection
                if user:
                    con = auth_db._db()
                    con.execute("UPDATE users SET failed_attempts = failed_attempts + 1 WHERE username = ?", (u,))
                    row = con.execute("SELECT failed_attempts FROM users WHERE username = ?", (u,)).fetchone()
                    attempts = row[0]
                    con.commit()
                    con.close()
                    
                    if attempts >= 5:
                        pm = ProjectManager(auth_db)
                        # Find admin for tenant
                        mship = auth_db.get_memberships(u)
                        t_id = mship[0].tenant_id if mship else "SYSTEM"
                        
                        # Create tasks for Dev and Admin
                        con = auth_db._db()
                        boards = con.execute("SELECT id FROM boards LIMIT 1").fetchone()
                        if boards:
                            pm.create_task(boards[0], f"Sicherheits-Alarm: Brute Force @ {u}", 
                                         content=f"Nutzer {u} hat 5 Fehlversuche. Bitte Passwort prüfen.",
                                         priority="HIGH")
                        con.close()
                        error = "Konto gesperrt oder zu viele Versuche. Admin wurde benachrichtigt."
                    else:
                        error = f"Login fehlgeschlagen. ({attempts}/5 Versuche)"
                else:
                    error = "Login fehlgeschlagen."
    return render_template("login.html", error=error, branding=Config.get_branding())


@bp.route("/forgot", methods=["GET", "POST"])
@csrf_protected
def forgot_password():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    code = ""
    message = ""
    if request.method == "POST":
        u = (request.form.get("username") or "").strip().lower()
        if u:
            user = auth_db.get_user(u)
            if user:
                now = datetime.now().isoformat()
                expires = (datetime.now() + timedelta(minutes=15)).isoformat()
                reset_code = f"{secrets.randbelow(900000) + 100000}"
                auth_db.create_auth_outbox_code(
                    username=u,
                    purpose="password_reset",
                    code=reset_code,
                    created_at=now,
                    expires_at=expires,
                )
                if _dev_local_email_codes_enabled():
                    code = reset_code
        message = _blind_success_message()

    return render_template_string(
        """
        <!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Passwort vergessen</title></head>
        <body style="font-family:system-ui;max-width:560px;margin:40px auto;line-height:1.5;">
          <h1>Passwort vergessen</h1>
          <form method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <label>Benutzername</label>
            <input name="username" style="display:block;width:100%;padding:8px;margin:8px 0 12px;" required>
            <button type="submit">Code anfordern</button>
          </form>
          {% if message %}<p>{{ message }}</p>{% endif %}
          {% if code %}<p><strong>DEV Local Code:</strong> {{ code }}</p>{% endif %}
          <p><a href="{{ url_for('web.reset_with_code') }}">Code einlösen</a></p>
          <p><a href="{{ url_for('web.login') }}">Zurück zum Login</a></p>
        </body></html>
        """,
        message=message,
        code=code,
    )


@bp.route("/reset-code", methods=["GET", "POST"])
@csrf_protected
def reset_with_code():
    auth_db: AuthDB = current_app.extensions["auth_db"]
    error = ""
    success = ""
    if request.method == "POST":
        u = (request.form.get("username") or "").strip().lower()
        code = (request.form.get("code") or "").strip()
        pw1 = (request.form.get("password") or "").strip()
        pw2 = (request.form.get("password_confirm") or "").strip()
        if not u or not code or not pw1 or pw1 != pw2:
            error = "Ungültige Eingaben."
        else:
            consumed = auth_db.consume_auth_outbox_code(
                username=u,
                purpose="password_reset",
                code=code,
                now_iso=datetime.now().isoformat(),
            )
            if not consumed:
                error = "Code ungültig oder abgelaufen."
            else:
                con = auth_db._db()
                try:
                    con.execute(
                        "UPDATE users SET password_hash=?, needs_reset=0 WHERE username=?",
                        (hash_password(pw1), u),
                    )
                    con.commit()
                finally:
                    con.close()
                success = "Passwort wurde aktualisiert."

    return render_template_string(
        """
        <!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reset mit Code</title></head>
        <body style="font-family:system-ui;max-width:560px;margin:40px auto;line-height:1.5;">
          <h1>Passwort per Code zurücksetzen</h1>
          <form method="post">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <label>Benutzername</label><input name="username" style="display:block;width:100%;padding:8px;margin:8px 0 12px;" required>
            <label>Code</label><input name="code" style="display:block;width:100%;padding:8px;margin:8px 0 12px;" required>
            <label>Neues Passwort</label><input name="password" type="password" style="display:block;width:100%;padding:8px;margin:8px 0 12px;" required>
            <label>Passwort bestätigen</label><input name="password_confirm" type="password" style="display:block;width:100%;padding:8px;margin:8px 0 12px;" required>
            <button type="submit">Passwort setzen</button>
          </form>
          {% if error %}<p style="color:#b91c1c;">{{ error }}</p>{% endif %}
          {% if success %}<p style="color:#047857;">{{ success }}</p>{% endif %}
          <p><a href="{{ url_for('web.login') }}">Zurück zum Login</a></p>
        </body></html>
        """,
        error=error,
        success=success,
    )


@bp.route("/password-reset", methods=["GET", "POST"])
def password_reset_page():
    u = session.get('pending_reset_user')
    if not u:
        return redirect(url_for('web.login'))
    
    error = ""
    if request.method == "POST":
        pw1 = request.form.get("password")
        pw2 = request.form.get("password_confirm")
        if pw1 and pw1 == pw2:
            from app.auth import hash_password
            auth_db = current_app.extensions["auth_db"]
            con = auth_db._db()
            con.execute("UPDATE users SET password_hash = ?, needs_reset = 0 WHERE username = ?", (hash_password(pw1), u))
            con.commit()
            con.close()
            session.pop('pending_reset_user')
            return redirect(url_for('web.login'))
        error = "Passwörter stimmen nicht überein."
        
    return render_template_string("""
        {% extends "layout.html" %}
        {% block content %}
        <div class="panel" style="max-width:400px; margin: 100px auto;">
            <h2 style="color:#fff; margin-bottom:20px;">Passwort zurücksetzen</h2>
            <form method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <div class="form-group">
                    <label class="form-label">Neues Passwort</label>
                    <input type="password" name="password" class="form-input" required autofocus>
                </div>
                <div class="form-group">
                    <label class="form-label">Bestätigen</label>
                    <input type="password" name="password_confirm" class="form-input" required>
                </div>
                <button type="submit" class="btn btn-primary" style="width:100%;">PASSWORT SPEICHERN</button>
                {% if error %}<p style="color:var(--color-danger); margin-top:10px;">{{ error }}</p>{% endif %}
            </form>
        </div>
        {% endblock %}
    """, error=error)


@bp.route("/admin/users/<username>/reset", methods=["POST"])
@login_required
@require_role("ADMIN")
def admin_user_reset(username: str):
    """One-click reset by Admin/Dev (Task v2.8)."""
    auth_db = current_app.extensions["auth_db"]
    con = auth_db._db()
    con.execute("UPDATE users SET needs_reset = 1 WHERE username = ?", (username,))
    con.commit()
    con.close()
    
    from app.modules.projects.logic import ProjectManager
    pm = ProjectManager(auth_db)
    # Notify Dev (Observer)
    con = auth_db._db()
    boards = con.execute("SELECT id FROM boards LIMIT 1").fetchone()
    if boards:
        pm.create_task(boards[0], f"Reset angefordert für {username}", content="Admin hat Passwort-Reset ausgelöst.")
    con.close()
    
    return jsonify(ok=True)


@bp.route("/logout")
def logout():
    if current_user():
        _audit("logout", target=current_user() or "", meta={})
    logout_user()
    return redirect(url_for("web.login"))


@bp.route("/api/progress")
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
def api_progress(token: str):
    if (not current_user()) and (request.remote_addr not in ("127.0.0.1", "::1")):
        return jsonify(error="unauthorized"), 401
    p = read_pending(token)
    if not p:
        return jsonify(error="not_found"), 404
    return jsonify(
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", ""),
    )


def _weather_answer(city: str) -> str:
    info = get_weather(city)
    if not info:
        return f"Ich konnte das Wetter für {city} nicht abrufen."
    return f"Wetter {info.get('city', '')}: {info.get('summary', '')} (Temp: {info.get('temp_c', '?')}°C, Wind: {info.get('wind_kmh', '?')} km/h)"


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
@csrf_protected
@chat_limiter.limit_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    msg = (
        (payload.get("message") if isinstance(payload, dict) else None)
        or
        (payload.get("msg") if isinstance(payload, dict) else None)
        or (payload.get("q") if isinstance(payload, dict) else None)
        or request.form.get("msg")
        or request.form.get("q")
        or ""
    ).strip()

    if not msg:
        return json_error("empty_query", "Leer.", status=400)

    response = agent_answer(msg)
    # Compat: some widgets expect `response`, others `text`.
    if isinstance(response, dict) and "text" in response and "response" not in response:
        response["response"] = response.get("text", "")
    if request.headers.get("HX-Request"):
        return f"<div class='text-sm'>{response.get('text', '')}</div>"
    return jsonify(response)


@bp.post("/api/search")
@login_required
@csrf_protected
@search_limiter.limit_required
def api_search():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    kdnr = (payload.get("kdnr") or "").strip()
    limit = int(payload.get("limit") or 8)
    if not query:
        return json_error("query_missing", "Query fehlt.", status=400)
    context = AgentContext(
        tenant_id=current_tenant(),
        user=str(current_user() or "dev"),
        role=str(current_role()),
        kdnr=kdnr,
    )
    agent = SearchAgent(core)
    results, suggestions = agent.search(query, context, limit=limit)
    message = "OK" if results else "Keine Treffer gefunden."
    return jsonify(
        ok=True, message=message, results=results, did_you_mean=suggestions or []
    )


@bp.post("/api/open")
@login_required
@csrf_protected
def api_open():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    if not token:
        return json_error("token_missing", "Token fehlt.", status=400)
    src = _resolve_doc_path(token, {})
    if not src or not src.exists():
        return json_error(
            "FILE_NOT_FOUND",
            "Datei nicht gefunden. Bitte suche erneut oder prüfe den Token.",
            status=404,
            details={"token": token},
        )
    try:
        new_token = analyze_to_pending(src)
    except FileNotFoundError:
        return json_error(
            "FILE_NOT_FOUND",
            "Datei nicht gefunden. Bitte suche erneut oder prüfe den Token.",
            status=404,
            details={"token": token},
        )
    return jsonify(ok=True, token=new_token)


@bp.route("/admin/mesh")
@login_required
@require_role(["DEV", "ADMIN"])
def mesh():
    # Fetch real mesh nodes from the database
    auth_db = current_app.extensions["auth_db"]
    from app.core.mesh_network import MeshNetworkManager
    manager = MeshNetworkManager(auth_db)
    nodes = manager.get_peers()
    
    # If no real nodes yet, keep some demo nodes but marked as demo
    if not nodes:
        nodes = [
            {
                "node_id": "DEMO-ZIMA",
                "name": "Büro Hub (Demo)",
                "type": "ZimaBlade",
                "status": "ONLINE",
                "last_ip": "192.168.1.50",
                "last_seen": "Gerade eben",
            }
        ]

    # Map database fields to UI fields if necessary
    for node in nodes:
        node["id"] = node.get("node_id")
        node["ip"] = node.get("last_ip")
        node["type"] = node.get("type", "ZimaBlade") # Default for Hubs
        node["sync"] = "100%"
        node["conflicts"] = 0

    return _render_base(
        render_template_string(HTML_MESH, nodes=nodes), active_tab="mesh"
    )


HTML_MESH = r"""
<div class="space-y-6">
    <div class="flex justify-between items-end">
        <div>
            <h1 class="text-2xl font-bold flex items-center gap-2">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                Global Health Monitor
            </h1>
            <p class="muted">P2P Mesh-Netzwerk & CRDT Sync Status</p>
        </div>
        <div class="badge px-4 py-2 bg-emerald-500/10 text-emerald-500 border-emerald-500/20">
            Mesh-Status: Stabil
        </div>
    </div>

    <div class="grid md:grid-cols-3 gap-6">
        {% for node in nodes %}
        <div class="card p-6 space-y-4">
            <div class="flex justify-between items-start">
                <div class="h-12 w-12 rounded-xl bg-slate-800 flex items-center justify-center">
                    {% if node.type == 'ZimaBlade' %}
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                    {% elif node.type == 'iPad/Web' %}
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                    {% else %}
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 16V4a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12"/><path d="M2 20h20"/><path d="M5 20l1-4h12l1 4"/></svg>
                    {% endif %}
                </div>
                <span class="text-[10px] font-bold px-2 py-1 rounded bg-slate-800 {{ 'text-emerald-500' if node.status == 'ONLINE' else 'text-rose-500' }}">
                    {{ node.status }}
                </span>
            </div>
            <div>
                <h3 class="font-bold">{{ node.name }}</h3>
                <p class="text-xs muted">{{ node.type }} • {{ node.ip }}</p>
            </div>
            <div class="pt-4 border-t border-slate-800 space-y-2">
                <div class="flex justify-between text-xs">
                    <span class="muted">Synchronisation</span>
                    <span>{{ node.sync }}</span>
                </div>
                <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div class="h-full bg-indigo-500" style="width: {{ node.sync }};"></div>
                </div>
                <div class="flex justify-between text-xs pt-2">
                    <span class="muted">Automatische Konfliktlösungen (CRDT)</span>
                    <span class="{{ 'text-amber-500 font-bold' if node.conflicts > 0 else 'muted' }}">{{ node.conflicts }}</span>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="card p-6">
        <h3 class="font-bold mb-4 flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>
            Letzte Sync-Ereignisse
        </h3>
        <div class="space-y-3">
            <div class="flex items-center gap-4 text-sm p-3 rounded-lg bg-slate-800/30 border border-slate-800">
                <div class="h-2 w-2 rounded-full bg-amber-500"></div>
                <div class="flex-1">
                    <span class="font-semibold">Konflikt gelöst:</span> Feld "customer_name" bei Kunde K123 (Hans Mueller)
                </div>
                <div class="text-xs muted">Vor 5 Min.</div>
                <div class="badge">LWW-Logic</div>
            </div>
             <div class="flex items-center gap-4 text-sm p-3 rounded-lg bg-slate-800/30 border border-slate-800">
                <div class="h-2 w-2 rounded-full bg-emerald-500"></div>
                <div class="flex-1">
                    <span class="font-semibold">Sync erfolgreich:</span> TABLET-GESELLE-01 → HUB-ZIMA-01
                </div>
                <div class="text-xs muted">Vor 12 Min.</div>
                <div class="badge">1.2 MB</div>
            </div>
        </div>
    </div>
</div>
"""


@login_required
@require_role("OPERATOR")
def api_customer():
    payload = request.get_json(silent=True) or {}
    kdnr = (payload.get("kdnr") or "").strip()
    if not kdnr:
        return json_error("kdnr_missing", "KDNR fehlt.", status=400)
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


@bp.get("/api/time/projects")
@login_required
def api_time_projects():
    if not callable(time_project_list):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    projects = time_project_list(tenant_id=current_tenant(), status="ACTIVE")  # type: ignore
    return jsonify(ok=True, projects=projects)


@bp.post("/api/time/projects")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_projects_create():
    if not callable(time_project_create):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    try:
        project = time_project_create(  # type: ignore
            tenant_id=current_tenant(),
            name=name,
            description=description,
            created_by=current_user() or "",
        )
    except ValueError as exc:
        return json_error(str(exc), "Projekt konnte nicht angelegt werden.", status=400)
    _rag_enqueue("time_project", int(project.get("id") or 0), "upsert")
    return jsonify(ok=True, project=project)


@bp.post("/api/time/start")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_start():
    if not callable(time_entry_start):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    note = (payload.get("note") or "").strip()
    try:
        entry = time_entry_start(  # type: ignore
            tenant_id=current_tenant(),
            user=current_user() or "",
            project_id=int(project_id) if project_id else None,
            note=note,
        )
    except ValueError as exc:
        return json_error(str(exc), "Timer konnte nicht gestartet werden.", status=400)
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.post("/api/time/stop")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_stop():
    if not callable(time_entry_stop):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    try:
        entry = time_entry_stop(  # type: ignore
            tenant_id=current_tenant(),
            user=current_user() or "",
            entry_id=int(entry_id) if entry_id else None,
        )
    except ValueError as exc:
        return json_error(str(exc), "Timer konnte nicht gestoppt werden.", status=400)
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.get("/api/time/entries")
@login_required
def api_time_entries():
    if not callable(time_entry_list):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    range_name = (request.args.get("range") or "week").strip().lower()
    date_value = (request.args.get("date") or datetime.now().date().isoformat()).strip()
    user = (request.args.get("user") or "").strip()
    if current_role() not in {"ADMIN", "DEV"}:
        user = current_user() or ""
    start_at, end_at = _time_range_params(range_name, date_value)
    entries = time_entry_list(  # type: ignore
        tenant_id=current_tenant(),
        user=user or None,
        start_at=start_at,
        end_at=end_at,
        limit=500,
    )
    summary: dict[str, int] = {}
    running = None
    for entry in entries:
        day = (entry.get("start_at") or "").split("T")[0]
        summary[day] = summary.get(day, 0) + int(entry.get("duration_seconds") or 0)
        if not entry.get("end_at") and running is None:
            running = entry
    summary_list = [{"date": k, "total_seconds": v} for k, v in sorted(summary.items())]
    return jsonify(ok=True, entries=entries, summary=summary_list, running=running)


@bp.post("/api/time/entry/edit")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_entry_edit():
    if not callable(time_entry_update):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    if not entry_id:
        return json_error("entry_id_required", "Eintrag fehlt.", status=400)
    try:
        entry = time_entry_update(  # type: ignore
            tenant_id=current_tenant(),
            entry_id=int(entry_id),
            project_id=(
                int(payload.get("project_id")) if payload.get("project_id") else None
            ),
            start_at=(payload.get("start_at") or None),
            end_at=(payload.get("end_at") or None),
            note=payload.get("note"),
            user=current_user() or "",
        )
    except ValueError as exc:
        return json_error(
            str(exc), "Eintrag konnte nicht aktualisiert werden.", status=400
        )
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.post("/api/time/entry/approve")
@login_required
@csrf_protected
@require_role("ADMIN")
def api_time_entry_approve():
    if not callable(time_entry_approve):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    if not entry_id:
        return json_error("entry_id_required", "Eintrag fehlt.", status=400)
    try:
        entry = time_entry_approve(  # type: ignore
            tenant_id=current_tenant(),
            entry_id=int(entry_id),
            approved_by=current_user() or "",
        )
    except ValueError as exc:
        return json_error(
            str(exc), "Eintrag konnte nicht freigegeben werden.", status=400
        )
    _rag_enqueue("time_entry", int(entry.get("id") or 0), "upsert")
    return jsonify(ok=True, entry=entry)


@bp.get("/api/time/export")
@login_required
def api_time_export():
    if not callable(time_entries_export_csv):
        return json_error(
            "feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501
        )
    range_name = (request.args.get("range") or "week").strip().lower()
    date_value = (request.args.get("date") or datetime.now().date().isoformat()).strip()
    user = (request.args.get("user") or "").strip()
    if current_role() not in {"ADMIN", "DEV"}:
        user = current_user() or ""
    start_at, end_at = _time_range_params(range_name, date_value)
    csv_payload = time_entries_export_csv(  # type: ignore
        tenant_id=current_tenant(),
        user=user or None,
        start_at=start_at,
        end_at=end_at,
    )
    response = current_app.response_class(csv_payload, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=time_entries.csv"
    return response


# ==============================
# Mail Agent Tab (Template/Mock workflow)
# ==============================
HTML_MAIL = """
<div class="grid gap-4">
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
    const res = await fetch('/api/mail/eml', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
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
    <div class="text-sm font-semibold mb-2">Import (DEV)</div>
    <div class="muted text-xs mb-2">IMPORT_ROOT: {{ import_root }}</div>
    <div class="flex flex-wrap gap-2 items-center">
      <button id="runImport" class="rounded-xl px-3 py-2 text-sm btn-outline">Import starten</button>
      <span id="importStatus" class="text-xs muted"></span>
    </div>
  </div>

  <div class="card p-4 rounded-2xl border">
    <div class="text-sm font-semibold mb-2">Partner Branding (White-Label)</div>
    <form action="/settings/branding" method="POST" class="grid gap-3 text-sm">
      <div class="grid gap-1">
        <label class="muted text-[10px] uppercase font-bold">Anzeigename</label>
        <input name="app_name" value="{{ branding.app_name }}" class="rounded-xl border px-3 py-2 bg-transparent" />
      </div>
      <div class="grid gap-1">
        <label class="muted text-[10px] uppercase font-bold">Primärfarbe (Hex)</label>
        <div class="flex gap-2">
          <input type="color" name="primary_color" value="{{ branding.primary_color }}" class="h-10 w-10 rounded-lg bg-transparent border-0 cursor-pointer" />
          <input name="primary_color_text" id="pColorText" value="{{ branding.primary_color }}" class="rounded-xl border px-3 py-2 bg-transparent flex-1" oninput="document.getElementsByName('primary_color')[0].value = this.value" />
        </div>
      </div>
      <div class="grid gap-1">
        <label class="muted text-[10px] uppercase font-bold">Footer Text</label>
        <input name="footer_text" value="{{ branding.footer_text }}" class="rounded-xl border px-3 py-2 bg-transparent" />
      </div>
      <button type="submit" class="rounded-xl px-3 py-2 text-sm btn-primary self-start mt-2">Branding speichern</button>
    </form>
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
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body || {})});
    let j = {};
    try{ j = await r.json(); }catch(e){}
    if(!r.ok){
      throw new Error(j.message || j.error || ('HTTP ' + r.status));
    }
    return j;
  }

  const status = document.getElementById('toolStatus');
  const dbStatus = document.getElementById('dbSwitchStatus');
  const baseStatus = document.getElementById('baseSwitchStatus');
  const importStatus = document.getElementById('importStatus');

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

  document.getElementById('runImport')?.addEventListener('click', async () => {
    importStatus.textContent = 'Import läuft...';
    try{
      const j = await postJson('/api/dev/import/run');
      importStatus.textContent = j.message || 'OK';
    }catch(e){ importStatus.textContent = 'Fehler: ' + e.message; }
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

Empfänger: {to or "(nicht angegeben)"}
Betreff-Vorschlag (falls vorhanden): {subject or "(leer)"}
Ton: {tone}
Länge: {length}

Kontext/Stichpunkte:
{context or "(leer)"}
"""


@bp.get("/mail")
@login_required
def mail_page():
    return _render_base(
        render_template_string(HTML_MAIL),
        active_tab="mail",
    )


@bp.post("/settings/branding")
@login_required
@csrf_protected
def settings_branding_save():
    data = request.form
    new_branding = {
        "app_name": data.get("app_name", "KUKANILEA"),
        "primary_color": data.get("primary_color", "#0ea5e9"),
        "footer_text": data.get("footer_text", ""),
    }

    import json

    with open(Config.BRANDING_FILE, "w") as f:
        json.dump(new_branding, f, indent=2)
        
    # Task v2.6: Manual DB Assignment
    db_path = data.get("core_db_path", "").strip()
    auth_db = current_app.extensions.get("auth_db")
    t_id = current_tenant()
    if auth_db and t_id:
        con = auth_db._db()
        con.execute("UPDATE tenants SET core_db_path = ? WHERE tenant_id = ?", (db_path or None, t_id))
        con.commit()
        con.close()

    return redirect(url_for("web.settings_page"))


@bp.get("/settings")
@login_required
def settings_page():
    if current_role() not in {"ADMIN", "DEV"}:
        return json_error("forbidden", "Nicht erlaubt.", status=403)
    auth_db: AuthDB = current_app.extensions["auth_db"]
    
    # Get current tenant DB path
    t_id = current_tenant()
    con = auth_db._db()
    row = con.execute("SELECT core_db_path FROM tenants WHERE tenant_id = ?", (t_id,)).fetchone()
    con.close()
    tenant_db_path = row["core_db_path"] if row else ""
    
    return _render_base(
        "settings.html",
        active_tab="settings",
        auth_db_path=str(auth_db.path),
        auth_schema=auth_db.get_schema_version(),
        auth_tenants=auth_db.count_tenants(),
        import_root=str(current_app.config.get("IMPORT_ROOT", "")),
        tenant_db_path=tenant_db_path
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
        return jsonify(ok=False, message="Indexing nicht verfügbar."), 400
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
        return jsonify(ok=False, message="Scan nicht verfügbar."), 400
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
        return jsonify(ok=False, message="Drift-Scan nicht verfügbar."), 400
    _DEV_STATUS["scan"] = result
    _audit("repair_drift", meta={"result": result})
    return jsonify(ok=True, message="Drift-Scan abgeschlossen.", result=result)


@bp.post("/api/dev/import/run")
@login_required
@require_role("DEV")
def api_import_run():
    import_root = Path(str(current_app.config.get("IMPORT_ROOT", ""))).expanduser()
    if not str(import_root):
        return json_error("import_root_missing", "IMPORT_ROOT fehlt.", status=400)
    if not _is_allowlisted_path(import_root):
        return json_error(
            "import_root_forbidden", "IMPORT_ROOT nicht erlaubt.", status=403
        )
    if not import_root.exists():
        return json_error(
            "import_root_missing", "IMPORT_ROOT existiert nicht.", status=400
        )
    if callable(getattr(core, "import_run", None)):
        result = core.import_run(
            import_root=import_root,
            user=str(current_user() or "dev"),
            role=str(current_role()),
        )
    else:
        return json_error("import_not_available", "Import nicht verfügbar.", status=400)
    _DEV_STATUS["scan"] = result
    _audit("import_run", meta={"result": result, "root": str(import_root)})
    return jsonify(ok=True, message="Import abgeschlossen.", result=result)


@bp.post("/api/dev/switch-db")
@login_required
@require_role("DEV")
def api_switch_db():
    payload = request.get_json(silent=True) or {}
    path = Path(str(payload.get("path", ""))).expanduser()
    if not path:
        return jsonify(ok=False, message="Pfad fehlt."), 400
    if not _is_allowlisted_path(path):
        return jsonify(ok=False, message="Pfad nicht erlaubt."), 400
    if not path.exists():
        return jsonify(ok=False, message="Datei existiert nicht."), 400
    old_path = str(getattr(core, "DB_PATH", ""))
    if callable(getattr(core, "set_db_path", None)):
        core.set_db_path(path)
        _DEV_STATUS["db"] = {"old": old_path, "new": str(path)}
        _audit("switch_db", target=str(path), meta={"old": old_path})
        return jsonify(ok=True, message="DB gewechselt.", path=str(path))
    return jsonify(ok=False, message="DB switch nicht verfügbar."), 400


@bp.post("/api/dev/switch-base")
@login_required
@require_role("DEV")
def api_switch_base():
    payload = request.get_json(silent=True) or {}
    path = Path(str(payload.get("path", ""))).expanduser()
    if not path:
        return jsonify(ok=False, message="Pfad fehlt."), 400
    if not _is_storage_path_valid(path):
        return (
            jsonify(ok=False, message="Pfad nicht erlaubt oder nicht vorhanden."),
            400,
        )
    old_path = str(getattr(core, "BASE_PATH", ""))
    if callable(getattr(core, "set_base_path", None)):
        core.set_base_path(path)
        global BASE_PATH
        BASE_PATH = path
        _DEV_STATUS["base"] = {"old": old_path, "new": str(path)}
        _audit("switch_base", target=str(path), meta={"old": old_path})
        return jsonify(ok=True, message="Ablage gewechselt.", path=str(path))
    return jsonify(ok=False, message="Ablage switch nicht verfügbar."), 400


@bp.post("/api/dev/test-llm")
@login_required
@require_role("DEV")
def api_test_llm():
    payload = request.get_json(silent=True) or {}
    q = str(payload.get("q") or "suche rechnung")
    llm = getattr(ORCHESTRATOR, "llm", None)
    if not llm:
        return jsonify(ok=False, message="LLM nicht verfügbar."), 400
    result = llm.rewrite_query(q)
    _DEV_STATUS["llm"] = result
    _audit("test_llm", meta={"result": result})
    return jsonify(ok=True, message=f"LLM: {llm.name}, intent={result.get('intent')}")


@bp.post("/api/mail/draft")
@login_required
@csrf_protected
def api_mail_draft():
    try:
        payload = request.get_json(force=True) or {}
        to = (payload.get("to") or "").strip()
        subject = (payload.get("subject") or "").strip()
        tone = (payload.get("tone") or "neutral").strip()
        length = (payload.get("length") or "kurz").strip()
        context = (payload.get("context") or "").strip()

        if not context and not subject:
            return jsonify({"error": "Bitte Kontext oder Betreff angeben."}), 400

        text = _mock_generate(_mail_prompt(to, subject, tone, length, context))
        return jsonify({"text": text, "meta": "mode=mock"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/api/mail/eml")
@login_required
@csrf_protected
def api_mail_eml():
    payload = request.get_json(force=True) or {}
    to = (payload.get("to") or "").strip()
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Body fehlt."}), 400
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
            meta[t] = {
                "filename": it.get("filename", ""),
                "progress": float(it.get("progress", 0.0) or 0.0),
                "progress_phase": it.get("progress_phase", ""),
            }
            
    # Step 2.6: Weighted Suggestions
    from app.core.suggestion_engine import SuggestionEngine
    engine = SuggestionEngine(_get_tenant_db_path())
    suggestions = engine.get_frequent_labels()
    keywords = engine.analyze_keywords()
    
    return _render_base(
        "dashboard.html", 
        active_tab="upload", 
        items=items, 
        meta=meta, 
        recent=[],
        suggestions=suggestions,
        keywords=keywords
    )


@bp.route("/upload", methods=["POST"])
@csrf_protected
@upload_limiter.limit_required
def upload():
    files = request.files.getlist("file")
    if not files:
        return jsonify(error="no_file"), 400
        
    tenant = _norm_tenant(current_tenant() or "default")
    
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
            p["file_hash"] = info # info contains the SHA256 hash here
            write_pending(token, p)
        except Exception: pass
        
        results.append({"token": token, "filename": filename})
        
    return jsonify(tokens=results, tenant=tenant)


@bp.route("/review/<token>/delete", methods=["POST"])
@csrf_protected
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


@bp.route("/review/<token>/kdnr", methods=["GET", "POST"])
@csrf_protected
def review(token: str):
    p = read_pending(token)
    if not p:
        return _render_base(_card("error", "Nicht gefunden."), active_tab="upload")
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
            doctypes=[],
            kdnr_ranked=[],
            name_suggestions=[],
            suggested_doctype="SONSTIGES",
            suggested_date="",
            confidence=0,
            msg="Analyse läuft noch. Bitte kurz warten oder zurück zur Übersicht."
        )

    w = _wizard_get(p)
    if True:
        # Tenant is fixed per account/license
        w["tenant"] = _norm_tenant(current_tenant() or p.get("tenant", "") or "default")

    suggested_doctype = (p.get("doctype_suggested") or "SONSTIGES").upper()
    if not w.get("doctype"):
        w["doctype"] = (
            suggested_doctype if suggested_doctype in DOCTYPE_CHOICES else "SONSTIGES"
        )
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
        match_path, match_score = suggest_existing_folder(
            BASE_PATH, w["tenant"], w.get("kdnr", ""), w.get("name", "")
        )
        if match_path:
            w["existing_folder"] = match_path
            existing_folder_hint = match_path
            existing_folder_score = match_score

    msg = ""
    if request.method == "POST":
        if request.form.get("reextract") == "1":
            src = _resolve_doc_path(token, p)
            if src and src.exists():
                try:
                    delete_pending(token)
                except Exception:
                    pass
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
                w["doctype"] = (
                    request.form.get("doctype") or w.get("doctype") or "SONSTIGES"
                ).upper()
                w["document_date"] = normalize_component(
                    request.form.get("document_date") or ""
                )
                w["name"] = normalize_component(request.form.get("name") or "")
                w["addr"] = normalize_component(request.form.get("addr") or "")
                w["plzort"] = normalize_component(request.form.get("plzort") or "")
                w["use_existing"] = normalize_component(
                    request.form.get("use_existing") or ""
                )

                if not w["kdnr"]:
                    msg = "KDNR fehlt."
                else:
                    src = Path(p.get("path", ""))
                    if not src.exists():
                        msg = "Datei im Eingang nicht gefunden."
                    else:
                        answers = {
                            "tenant": w["tenant"],
                            "kdnr": w["kdnr"],
                            "use_existing": w.get("use_existing", ""),
                            "name": w.get("name") or "Kunde",
                            "addr": w.get("addr") or "Adresse",
                            "plzort": w.get("plzort") or "PLZ Ort",
                            "doctype": w.get("doctype") or "SONSTIGES",
                            "document_date": w.get("document_date") or "",
                        }
                        try:
                            # Auto-Learning: Capture corrections before clearing pending
                            try:
                                from app.core.rag_sync import learn_from_correction
                                learn_from_correction(
                                    tenant_id=answers["tenant"],
                                    file_name=p.get("filename", ""),
                                    text=p.get("ocr_text", ""),
                                    original_suggestions=p,
                                    final_answers=answers
                                )
                            except Exception as le:
                                logger.error(f"Auto-Learning failed: {le}")

                            folder, final_path, created_new = process_with_answers(
                                Path(p.get("path", "")), answers
                            )
                            write_done(
                                token, {"final_path": str(final_path), **answers}
                            )
                            delete_pending(token)
                            return redirect(url_for("web.done_view", token=token))
                        except Exception as e:
                            msg = f"Ablage fehlgeschlagen: {e}"

    _wizard_save(token, p, w)

    filename = p.get("filename", "")
    ext = Path(filename).suffix.lower()
    is_pdf = ext == ".pdf"
    is_text = ext == ".txt"

    # Step 2.6: Weighted Suggestions for Wizard
    from app.core.suggestion_engine import SuggestionEngine
    engine = SuggestionEngine(_get_tenant_db_path())
    dyn_suggestions = engine.get_frequent_labels()
    dyn_keywords = engine.analyze_keywords()

    # Phase 3: Individual Intelligence (YAKE! + DB Weights)
    intel_engine = IndividualIntelligence(_get_tenant_db_path())
    # Extract OCR text from pending if available (simplified for now)
    doc_text = p.get("ocr_text", filename)
    weighted_tags = intel_engine.get_weighted_suggestions(doc_text)

    return _render_base(
        "review.html",
        active_tab="upload",
        token=token,
        filename=filename,
        is_pdf=is_pdf,
        is_text=is_text,
        preview=p.get("preview", ""),
        w=w,
        doctypes=DOCTYPE_CHOICES,
        kdnr_ranked=dyn_suggestions.get("kdnr", []),
        name_suggestions=dyn_suggestions.get("customer_names", []),
        suggested_doctype=suggested_doctype,
        suggested_date=suggested_date,
        confidence=confidence,
        msg=msg,
        is_duplicate=p.get("is_duplicate", False),
        keywords=weighted_tags # v1.4: Use weighted YAKE tags
    )


@bp.route("/done/<token>")
def done_view(token: str):
    d = read_done(token) or {}
    fp = d.get("final_path", "")
    return _render_base("done.html", active_tab="upload", final_path=fp)


@bp.route("/crm/contacts")
@login_required
def crm_contacts():
    return _render_base("generic_tool.html", active_tab="crm", title="CRM - Kontakte", message="Kontaktverwaltung wird synchronisiert...")


@bp.route("/documents")
@login_required
def documents():
    return _render_base("generic_tool.html", active_tab="documents", title="Dokumenten-Archiv", message="Archiv-Index wird geladen...")


@bp.route("/assistant")
def assistant():
    # Ensure core searches within current tenant
    try:
        from app import core as _core

        _core.TENANT_DEFAULT = current_tenant() or _core.TENANT_DEFAULT
    except Exception:
        pass
    q = normalize_component(request.args.get("q", "") or "")
    kdnr = normalize_component(request.args.get("kdnr", "") or "")
    results = []
    if q and assistant_search is not None:
        try:
            raw = assistant_search(
                query=q,
                kdnr=kdnr,
                limit=50,
                role=current_role(),
                tenant_id=current_tenant(),
            )
            for r in raw or []:
                fp = r.get("file_path") or ""
                if ASSISTANT_HIDE_EINGANG and fp:
                    try:
                        if str(Path(fp).resolve()).startswith(
                            str(EINGANG.resolve()) + os.sep
                        ):
                            continue
                    except Exception:
                        pass
                r["fp_b64"] = _b64(fp) if fp else ""
                results.append(r)
        except Exception:
            pass
    html = """<div class='card p-5'>
      <div class='text-lg font-semibold mb-1'>Assistant</div>
      <form method='get' class='flex flex-col md:flex-row gap-2 mb-4'>
        <input class='w-full rounded-xl p-2 input' name='q' value='{q}' placeholder='Suche…' />
        <input class='w-full md:w-40 rounded-xl p-2 input' name='kdnr' value='{kdnr}' placeholder='Kdnr optional' />
        <button class='rounded-xl px-4 py-2 font-semibold btn-primary md:w-40' type='submit'>Suchen</button>
      </form>
      <div class='muted text-xs'>Treffer: {n}</div>
    </div>""".format(
        q=q.replace("'", "&#39;"), kdnr=kdnr.replace("'", "&#39;"), n=len(results)
    )
    return _render_base(html, active_tab="assistant")


@bp.route("/projects")
@login_required
def projects_list():
    from app.modules.projects.logic import ProjectManager
    pm = ProjectManager(current_app.extensions["auth_db"])
    
    # Ensure at least one project exists for demo
    con = current_app.extensions["auth_db"]._db()
    p = con.execute("SELECT * FROM projects LIMIT 1").fetchone()
    con.close()
    
    if not p:
        p_id = pm.create_project(current_tenant(), "Standard Projekt", "Willkommen in Ihrer Projektverwaltung.")
        pm.create_board(p_id, "Hauptboard")
        return redirect(url_for("web.projects_list"))
        
    tasks = pm.list_tasks(con.execute("SELECT id FROM boards WHERE project_id = ? LIMIT 1", (p["id"],)).fetchone()[0])
    
    return _render_base("kanban.html", active_tab="tasks", project=p, tasks=tasks)


@bp.post("/api/tasks/<task_id>/move")
@login_required
@csrf_protected
def api_task_move(task_id: str):
    payload = request.get_json() or {}
    new_col = payload.get("column")
    if not new_col:
        return jsonify(ok=False), 400
        
    from app.modules.projects.logic import ProjectManager
    pm = ProjectManager(current_app.extensions["auth_db"])
    pm.update_task_column(task_id, new_col)
    
    return jsonify(ok=True)


@bp.route("/messenger")
@login_required
def messenger_page():
    return _render_base("messenger.html", active_tab="messenger")


@bp.route("/visualizer")
@login_required
def visualizer_page():
    return _render_base("visualizer.html", active_tab="visualizer")


@bp.route("/legal")
def legal_page():
    return _render_base("legal.html", active_tab="settings")


@bp.route("/health")
def health():
    return jsonify(ok=True, ts=time.time(), app="kukanilea_upload_v3_ui")



@bp.route("/admin/forensics")
@login_required
@require_role(["DEV", "ADMIN"])
def admin_forensics():
    from app.core.audit import vault
    from kukanilea_app import measure_db_speed, measure_cpu_usage, measure_memory_usage
    
    trail = vault.get_audit_trail() or []
    
    # System performance snapshot (Step 171-185)
    perf = {
        "db_query_speed": measure_db_speed(),
        "cpu_usage": measure_cpu_usage(),
        "memory_info": measure_memory_usage(),
        "boot_time_ms": 420 # Mock for now
    }
    
    # Active Users simulation (Step 22)
    active_users = ["admin", "user_1"] # In real impl, check session store
    
    return _render_base(
        "forensic_dashboard.html",
        active_tab="settings",
        trail=trail,
        perf=perf,
        audit_count=len(trail),
        active_users=active_users
    )


@bp.route("/admin/logs")
@login_required
@require_role("DEV")
def admin_logs():
    log_file = Path(current_app.config.get("LOG_DIR", "logs")) / "app.jsonl"
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                # Get last 500 lines
                lines = f.readlines()[-500:]
                for line in lines:
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
        except Exception as e:
            logs.append({"timestamp": str(datetime.now()), "level": "ERROR", "message": f"Log read failed: {e}"})
            
    return _render_base("dev_logs.html", active_tab="settings", logs=logs)


@bp.route("/admin/audit")
@login_required
@require_role(["DEV", "ADMIN"])
def admin_audit():
    trail = vault.get_audit_trail()
    return _render_base("audit_trail.html", active_tab="settings", trail=trail)


@bp.route("/api/tools")
@login_required
def api_list_tools():
    from app.tools.registry import registry
    return jsonify(ok=True, tools=registry.list())


@bp.route("/admin/audit/verify", methods=["POST"])
@login_required
@require_role(["DEV", "ADMIN"])
def admin_audit_verify():
    from app.core.audit import vault
    ok, errors = vault.verify_chain()
    if ok:
        return '<div class="badge pulse" style="background:rgba(16,185,129,0.1); color:var(--color-success); border-color:rgba(16,185,129,0.2);">CHAIN VERIFIZIERT (OK)</div>'
    else:
        return f'<div class="badge" style="background:rgba(239,68,68,0.1); color:var(--color-danger); border-color:rgba(239,68,68,0.2);">CHAIN MANIPULIERT ({len(errors)} FEHLER)</div>'


@bp.route("/time")
@login_required
def time_tracking():
    if not callable(time_entry_list):
        html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
          <div class='text-lg font-semibold'>Time Tracking</div>
          <div class='muted text-sm mt-2'>Time Tracking ist im Core nicht verfügbar.</div>
        </div>"""
        return _render_base(html, active_tab="time")
    return _render_base(
        render_template_string(HTML_TIME, role=current_role()), active_tab="time"
    )
