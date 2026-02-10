#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tophandwerk Upload/UI (v2.2 compatible) + Tenant/Mandant support (v2.2+)

NEU (Tenant/Mandant):
- Mandant/Firma wird beim Upload gesetzt und im Pending/Wizard gespeichert
- Eingang wird tenant-spezifisch: EINGANG/<tenant>/...
- Finalize übergibt answers["tenant"] an process_with_answers
- Optional: Mandant ist Pflicht (default: ja), Allowlist möglich

ENV:
  TOPHANDWERK_TENANT_REQUIRE=1           # 1=Pflicht (default), 0=optional
  TOPHANDWERK_TENANT_DEFAULT=firma_x     # optionaler Fallback
  TOPHANDWERK_TENANTS=firma_x,firma_y    # optional Allowlist (lowercase)
"""

import base64
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    session,
    url_for,
)

try:
    from werkzeug.utils import secure_filename
except Exception:
    secure_filename = None  # type: ignore

import tophandwerk_core as core


# ============================================================
# Robust core access
# ============================================================
def _core_get(name, default=None):
    return getattr(core, name, default)


EINGANG: Path = _core_get("EINGANG")
BASE_PATH: Path = _core_get("BASE_PATH")
PENDING_DIR: Path = _core_get("PENDING_DIR")
DONE_DIR: Path = _core_get("DONE_DIR")
SUPPORTED_EXT = _core_get(
    "SUPPORTED_EXT", {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".txt"}
)

analyze_to_pending = _core_get("analyze_to_pending") or _core_get(
    "start_background_analysis"
)
read_pending = _core_get("read_pending")
write_pending = _core_get("write_pending")
delete_pending = _core_get("delete_pending")
list_pending = _core_get("list_pending")
resolve_source_path = _core_get("resolve_source_path")
write_done = _core_get("write_done")
read_done = _core_get("read_done")
process_with_answers = _core_get("process_with_answers")
normalize_component = _core_get("normalize_component")

find_existing_customer_folders = _core_get("find_existing_customer_folders")
parse_folder_fields = _core_get("parse_folder_fields")
best_match_object_folder = _core_get("best_match_object_folder")

detect_object_duplicates_for_kdnr = _core_get(
    "detect_object_duplicates_for_kdnr"
)  # optional

db_init = _core_get("db_init")
rbac_verify_user = _core_get("rbac_verify_user")
rbac_create_user = _core_get("rbac_create_user")
rbac_assign_role = _core_get("rbac_assign_role")
rbac_get_user_roles = _core_get("rbac_get_user_roles")
audit_log = _core_get("audit_log")
assistant_search = _core_get("assistant_search")

index_run_full = _core_get("index_run_full")  # optional
core_parse_excel_like_date = _core_get("parse_excel_like_date")  # optional


# guard rails (minimum contract)
REQUIRED = {
    "EINGANG": EINGANG,
    "BASE_PATH": BASE_PATH,
    "PENDING_DIR": PENDING_DIR,
    "DONE_DIR": DONE_DIR,
    "analyze_to_pending/start_background_analysis": analyze_to_pending,
    "read_pending": read_pending,
    "write_pending": write_pending,
    "delete_pending": delete_pending,
    "list_pending": list_pending,
    "write_done": write_done,
    "read_done": read_done,
    "process_with_answers": process_with_answers,
    "normalize_component": normalize_component,
}
_missing = [k for k, v in REQUIRED.items() if v is None]
if _missing:
    raise RuntimeError(f"Core-Contract unvollständig, fehlt: {', '.join(_missing)}")


# ============================================================
# Flask
# ============================================================
APP = Flask(__name__)
APP.secret_key = os.environ.get(
    "TOPHANDWERK_SECRET", "tophandwerk-dev-secret-change-me"
)
PORT = int(os.environ.get("PORT", 5051))

# Optional hard upload limit (bytes)
APP.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("TOPHANDWERK_MAX_UPLOAD", str(25 * 1024 * 1024))
)

BOOTSTRAP_ADMIN_USER = os.environ.get("TOPHANDWERK_ADMIN_USER", "").strip().lower()
BOOTSTRAP_ADMIN_PASS = os.environ.get("TOPHANDWERK_ADMIN_PASS", "").strip()

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

# Assistant: Eingang ist NICHT sichtbar (nur Hintergrund)
ASSISTANT_HIDE_EINGANG = True

# ============================================================
# Tenant/Mandant Config
# ============================================================
TENANT_DEFAULT = os.environ.get("TOPHANDWERK_TENANT_DEFAULT", "").strip()
TENANT_REQUIRE = os.environ.get("TOPHANDWERK_TENANT_REQUIRE", "1").strip() == "1"
TENANT_ALLOWLIST = [
    x.strip().lower()
    for x in os.environ.get("TOPHANDWERK_TENANTS", "").split(",")
    if x.strip()
]


# ============================================================
# Helpers
# ============================================================
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode((s or "").encode("utf-8")).decode("ascii")


def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode((s or "").encode("ascii")).decode(
        "utf-8", errors="ignore"
    )


def _logged_in() -> bool:
    # wenn RBAC nicht vorhanden: lasse alles zu (degraded dev mode)
    if rbac_verify_user is None:
        return True
    return bool(session.get("user"))


def _current_user() -> str:
    if rbac_verify_user is None:
        return "dev"
    return str(session.get("user") or "")


def _current_roles() -> list:
    if rbac_verify_user is None:
        return ["DEV"]
    return session.get("roles") or []


def _has_role(role: str) -> bool:
    role = (role or "").upper()
    return role in [str(r).upper() for r in _current_roles()]


def _audit(action: str, target: str = "", meta: dict = None):
    if audit_log is None:
        return
    u = _current_user()
    roles = _current_roles()
    role = roles[0] if roles else ""
    try:
        audit_log(user=u, role=role, action=action, target=target, meta=meta or {})
    except Exception:
        pass


def _ensure_bootstrap_admin():
    # nur wenn RBAC implementiert ist
    if (
        rbac_verify_user is None
        or rbac_create_user is None
        or rbac_assign_role is None
        or rbac_get_user_roles is None
    ):
        return
    if not (BOOTSTRAP_ADMIN_USER and BOOTSTRAP_ADMIN_PASS):
        return
    try:
        if rbac_verify_user(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS):
            return
        uid = rbac_create_user(BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASS)
        rbac_assign_role(BOOTSTRAP_ADMIN_USER, "ADMIN")
        _audit("bootstrap_admin", target=str(uid), meta={"user": BOOTSTRAP_ADMIN_USER})
    except Exception:
        pass


def _safe_filename(name: str) -> str:
    raw = (name or "").strip().replace("\\", "_").replace("/", "_")
    if secure_filename is not None:
        out = secure_filename(raw)
        return out or "upload"
    raw = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw)
    raw = raw.strip("._-")
    return raw or "upload"


def _is_allowed_ext(filename: str) -> bool:
    try:
        return Path(filename).suffix.lower() in set(SUPPORTED_EXT)
    except Exception:
        return False


def _allowed_roots() -> List[Path]:
    # dynamic roots (avoid stale roots if core config changes)
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
            if str(rp).startswith(str(root) + os.sep) or rp == root:
                return True
        return False
    except Exception:
        return False


def _render_base(content: str, active_tab: str = "upload"):
    return render_template_string(
        HTML_BASE,
        content=content,
        eingang=str(EINGANG),
        ablage=str(BASE_PATH),
        user=_current_user() or "-",
        roles=", ".join(_current_roles()) or "-",
        active_tab=active_tab,
    )


def _card_error(msg: str) -> str:
    return f"""
      <div class="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm">
        {msg}
      </div>
    """


def _card_warn(msg: str) -> str:
    return f"""
      <div class="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
        {msg}
      </div>
    """


def _card_info(msg: str) -> str:
    return f"""
      <div class="rounded-xl border border-slate-700 bg-slate-950/40 p-3 text-sm">
        {msg}
      </div>
    """


def _norm_tenant(t: str) -> str:
    try:
        t = normalize_component(t or "")
    except Exception:
        t = (t or "").strip()
    t = t.lower().replace(" ", "_")
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
    w.setdefault("tenant", "")  # NEW
    w.setdefault("kdnr", "")
    w.setdefault("use_existing", "")
    w.setdefault("name", "")
    w.setdefault("addr", "")
    w.setdefault("plzort", "")
    w.setdefault("doctype", "")
    w.setdefault("document_date", "")  # optional in v2.2
    w.setdefault("customer_status", "")  # "BESTAND" / "NEU"
    w.setdefault("adopt_existing", True)  # UI default: übernehmen
    return w


def _wizard_save(token: str, p: dict, w: dict):
    p["wizard"] = w
    write_pending(token, p)


# --- Date parsing (prefer core, else local) ---
_DATE_PATTERNS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
]


def parse_excel_like_date(s: Any) -> str:
    if callable(core_parse_excel_like_date):
        try:
            return str(core_parse_excel_like_date(s) or "")
        except Exception:
            pass

    if not s:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).replace("T", " ")

    for pat in _DATE_PATTERNS:
        try:
            dt = datetime.strptime(s, pat)
            d = dt.date()
            if d.year < 1900 or d.year > 2099:
                return ""
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        try:
            y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d = date(y, mo, da)
            if d.year < 1900 or d.year > 2099:
                return ""
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if m:
        try:
            da, mo = int(m.group(1)), int(m.group(2))
            y = int(m.group(3))
            if y < 100:
                y = 2000 + y if y <= 68 else 1900 + y
            d = date(y, mo, da)
            if d.year < 1900 or d.year > 2099:
                return ""
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    return ""


def _predict_filename(w: dict, suggested: str) -> str:
    """
    v2.2: doc_date OPTIONAL (no fallback to today).
    """
    dt_raw = (w.get("document_date") or "").strip()
    dt = parse_excel_like_date(dt_raw) or ""  # optional

    doctype = (w.get("doctype") or suggested or "SONSTIGES").upper()
    kdnr = (w.get("kdnr") or "").strip()
    name = (w.get("name") or "").strip()
    addr = (w.get("addr") or "").strip()
    plzort = (w.get("plzort") or "").strip()

    code = {
        "RECHNUNG": "RE",
        "ANGEBOT": "ANG",
        "AUFTRAGSBESTAETIGUNG": "AB",
        "AW": "AW",
        "MAHNUNG": "MAH",
        "NACHTRAG": "NTR",
        "FOTO": "FOTO",
        "H_RECHNUNG": "H_RE",
        "H_ANGEBOT": "H_ANG",
        "SONSTIGES": "DOC",
    }.get(doctype, "DOC")

    parts = [code]
    if dt:
        parts.append(dt)

    for x in [kdnr, name, addr, plzort]:
        if x:
            parts.append(x)

    s = "_".join(parts)
    s = re.sub(r"\s+", "_", s).strip("_")
    s = re.sub(r"_+", "_", s)
    s = s[:120]
    return s + ".[ext]"


# ============================================================
# UI Templates
# ============================================================
HTML_BASE = r"""
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tophandwerk</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
  const savedTheme = localStorage.getItem("th_theme") || "dark";
  const savedAccent = localStorage.getItem("th_accent") || "indigo";
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
  .pickbtn{
    border: 1px solid rgba(148,163,184,.25);
    background: rgba(2,6,23,.35);
    color: #e2e8f0;
  }
  .pickbtn:hover{ border-color: rgba(148,163,184,.55); }

  .light body { background:#f8fafc !important; color:#0f172a !important; }
  .light .card { background:rgba(255,255,255,.95) !important; border-color:#e2e8f0 !important; }
  .light .muted { color:#475569 !important; }
  .light .input { background:#ffffff !important; border-color:#cbd5e1 !important; color:#0f172a !important; }
  .light .btn-outline{ border-color:#cbd5e1 !important; }
  .light .pickbtn{ background:#ffffff !important; color:#0f172a !important; border-color:#cbd5e1 !important; }

  .accentText{ color:var(--accent-500); }
  .tab { border:1px solid rgba(148,163,184,.25); }
  .tab.active { border-color: rgba(148,163,184,.55); background: rgba(2,6,23,.35); }
  .light .tab.active { background:#ffffff !important; }
</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
<div class="max-w-7xl mx-auto p-6">
  <div class="flex items-start justify-between gap-3 mb-6">
    <div>
      <h1 class="text-3xl font-bold">Tophandwerk</h1>
      <div class="muted text-sm">Upload → Review → Ablage • Assistant</div>
      <div class="muted text-xs mt-1">Ablage: {{ablage}}</div>
    </div>

    <div class="flex items-center gap-2">
      <div class="text-right">
        <div class="text-xs muted">Login</div>
        <div class="text-sm font-semibold">{{user}}</div>
        <div class="text-[11px] muted">{{roles}}</div>
      </div>
      {% if user != 'dev' %}
      <a class="rounded-xl px-3 py-2 text-sm card btn-outline" href="/logout">Logout</a>
      {% endif %}
      <button id="accentBtn" class="rounded-xl px-3 py-2 text-sm card btn-outline">
        Accent: <span id="accentLabel"></span>
      </button>
      <button id="themeBtn" class="rounded-xl px-3 py-2 text-sm card btn-outline">
        Theme: <span id="themeLabel"></span>
      </button>
    </div>
  </div>

  <div class="flex flex-wrap gap-2 mb-5">
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='upload' else ''}}" href="/">Upload/Queue</a>
    <a class="tab rounded-xl px-4 py-2 text-sm {{'active' if active_tab=='assistant' else ''}}" href="/assistant">Assistant</a>
  </div>

  {{ content|safe }}
</div>

<script>
(function(){
  const btnTheme = document.getElementById("themeBtn");
  const lblTheme = document.getElementById("themeLabel");
  const btnAcc = document.getElementById("accentBtn");
  const lblAcc = document.getElementById("accentLabel");

  function curTheme(){ return (localStorage.getItem("th_theme") || "dark"); }
  function curAccent(){ return (localStorage.getItem("th_accent") || "indigo"); }

  function applyTheme(t){
    if(t === "light"){ document.documentElement.classList.add("light"); }
    else { document.documentElement.classList.remove("light"); }
    localStorage.setItem("th_theme", t);
    lblTheme.textContent = t;
  }

  function applyAccent(a){
    document.documentElement.dataset.accent = a;
    localStorage.setItem("th_accent", a);
    lblAcc.textContent = a;
  }

  applyTheme(curTheme());
  applyAccent(curAccent());

  btnTheme?.addEventListener("click", ()=>{
    applyTheme(curTheme() === "dark" ? "light" : "dark");
  });

  btnAcc?.addEventListener("click", ()=>{
    const order = ["indigo","emerald","amber"];
    const i = order.indexOf(curAccent());
    applyAccent(order[(i+1) % order.length]);
  });
})();
</script>
</body>
</html>
"""

HTML_LOGIN = r"""
<div class="max-w-md mx-auto rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card">
  <div class="text-2xl font-bold mb-2">Login</div>
  <div class="muted text-sm mb-5">Bitte anmelden, um Tophandwerk zu nutzen.</div>

  {% if error %}
    <div class="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm mb-4">{{error}}</div>
  {% endif %}

  <form method="post" class="space-y-3" autocomplete="off">
    <div>
      <label class="muted text-xs">Username</label>
      <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="username" placeholder="username" />
    </div>
    <div>
      <label class="muted text-xs">Passwort</label>
      <input type="password" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="password" placeholder="••••••••" />
    </div>
    <button class="rounded-xl px-4 py-2 font-semibold btn-primary w-full" type="submit">Login</button>
  </form>

  <div class="muted text-xs mt-4">
    Reset/Account-Setup: Admin/Dev verwaltet.
  </div>
</div>
"""

HTML_INDEX = r"""
<div class="grid md:grid-cols-2 gap-6">
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Datei hochladen</div>
    <div class="muted text-sm mb-4">
      Unterstützt: PDF, JPG, PNG, TIFF, BMP, TXT. Upload → Analyse im Hintergrund → Review öffnet automatisch.
    </div>

    <form id="upform" class="space-y-3">
      <input id="file" name="file" type="file"
        class="block w-full text-sm input
        file:mr-4 file:rounded-xl file:border-0 file:bg-slate-700 file:px-4 file:py-2
        file:text-sm file:font-semibold file:text-white hover:file:bg-slate-600" />

      <input id="tenant" name="tenant" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input"
        placeholder="Mandant/Firma (z.B. firma_x)" />

      <button id="btn" type="submit" class="rounded-xl px-4 py-2 font-semibold btn-primary">
        Hochladen
      </button>
    </form>

    <div class="mt-4">
      <div class="text-xs muted mb-1" id="pLabel">0.0%</div>
      <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
        <div id="bar" class="h-3 w-0" style="background:var(--accent-500)"></div>
      </div>
      <div class="text-slate-300 text-sm mt-3" id="status"></div>
      <div class="muted text-xs mt-1" id="phase"></div>
    </div>

    {% if admin_tools %}
      <div class="mt-5 pt-4 border-t border-slate-800">
        <div class="text-sm font-semibold mb-2">Admin Tools</div>
        <button id="btnIndex" type="button" class="rounded-xl px-4 py-2 font-semibold btn-outline card">
          Vollscan Index (BASE_PATH)
        </button>
        <div class="muted text-xs mt-2" id="idxStatus"></div>
      </div>
      <script>
      (function(){
        const b = document.getElementById("btnIndex");
        const s = document.getElementById("idxStatus");
        if(!b) return;
        b.addEventListener("click", async ()=>{
          if(!confirm("Vollscan starten? Kann dauern.")) return;
          s.textContent = "Start…";
          try{
            const res = await fetch("/api/index_fullscan", {method:"POST"});
            const j = await res.json();
            if(!res.ok){ s.textContent = "Fehler: " + (j.error || ("HTTP " + res.status)); return; }
            s.textContent = "OK: indexed=" + j.indexed + " skipped=" + j.skipped + " errors=" + j.errors;
          }catch(e){
            s.textContent = "Netzwerk/Server-Fehler.";
          }
        });
      })();
      </script>
    {% endif %}
  </div>

  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Review Queue</div>
    <div class="muted text-sm mb-4">
      Dateien bleiben hier, bis sie bestätigt sind.
    </div>

    {% if items %}
      <div class="space-y-2">
        {% for it in items %}
          <div class="rounded-xl border border-slate-800 hover:border-slate-600 px-3 py-2">
            <div class="flex items-center justify-between gap-2">
              <a class="text-sm font-semibold underline accentText" href="/review/{{it}}/kdnr">
                Review öffnen
              </a>
              <div class="muted text-xs">{{meta[it].get('progress',0) | round(1)}}%</div>
            </div>
            <div class="muted text-xs break-all">{{meta[it].get('filename','')}}</div>
            <div class="muted text-[11px]">{{meta[it].get('progress_phase','')}}</div>
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
  const res = await fetch("/api/progress/" + token, {cache:"no-store"});
  const j = await res.json();
  setProgress(j.progress || 0);
  phase.textContent = j.progress_phase || "";
  if(j.status === "READY"){
    status.textContent = "Analyse fertig. Review öffnet…";
    setTimeout(()=>{ window.location.href = "/review/" + token + "/kdnr"; }, 120);
    return;
  }
  if(j.status === "ERROR"){
    status.textContent = "Analyse-Fehler: " + (j.error || "unbekannt");
    return;
  }
  setTimeout(()=>poll(token), 450);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = fileInput.files[0];
  if(!f){ status.textContent = "Bitte eine Datei auswählen."; return; }

  const ext = (f.name.split(".").pop() || "").toLowerCase();
  const ok = ["pdf","jpg","jpeg","png","tif","tiff","bmp","txt"].includes(ext);
  if(!ok){
    status.textContent = "Nicht unterstützt. Bitte PDF/JPG/PNG/TIFF/BMP/TXT hochladen.";
    return;
  }

  const tenant = (tenantInput?.value || "").trim();

  const fd = new FormData();
  fd.append("file", f);
  fd.append("tenant", tenant);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);

  xhr.upload.onprogress = (ev) => {
    if(ev.lengthComputable){
      setProgress((ev.loaded / ev.total) * 35);
      phase.textContent = "Upload…";
    }
  };

  xhr.onload = () => {
    if(xhr.status === 200){
      const resp = JSON.parse(xhr.responseText);
      status.textContent = "Upload OK. Analyse läuft…";
      poll(resp.token);
    } else {
      try{
        const j = JSON.parse(xhr.responseText || "{}");
        status.textContent = "Fehler beim Upload: " + (j.error || ("HTTP " + xhr.status));
      }catch(e){
        status.textContent = "Fehler beim Upload: HTTP " + xhr.status;
      }
    }
  };

  xhr.onerror = () => { status.textContent = "Upload fehlgeschlagen (Netzwerk/Server)."; };
  status.textContent = "Upload läuft…";
  setProgress(0);
  phase.textContent = "";
  xhr.send(fd);
});
</script>
"""

HTML_REVIEW_SHELL = r"""
<div class="grid md:grid-cols-2 gap-6">
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="text-lg font-semibold">Review</div>
        <div class="muted text-sm">Datei: {{filename}}</div>
        <div class="muted text-xs mt-1">{% if used_ocr %}OCR aktiv{% else %}Text-Extract{% endif %}</div>
      </div>
      <div class="flex items-center gap-3">
        <a class="text-sm underline accentText" href="/file/{{token}}" target="_blank">Datei öffnen</a>
        <a class="text-sm underline muted" href="/">Zurück</a>
      </div>
    </div>

    <div class="mt-4 rounded-xl border border-slate-800 overflow-hidden">
      {% if is_pdf %}
        <iframe src="/file/{{token}}" class="w-full" style="height:560px"></iframe>
      {% elif is_text %}
        <iframe src="/file/{{token}}" class="w-full" style="height:560px"></iframe>
      {% else %}
        <img src="/file/{{token}}" class="w-full"/>
      {% endif %}
    </div>

    {% if preview %}
      <div class="mt-4">
        <div class="text-sm font-semibold mb-2">Beschriftungs-/Text-Vorschau (Kontrolle)</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-3 bg-slate-950/40 max-h-52 overflow-auto">{{preview}}</pre>
      </div>
    {% endif %}
  </div>

  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="muted text-xs mb-2">Voraussichtlicher Dateiname</div>
    <div class="text-sm font-semibold break-all accentText mb-4">{{predicted_name}}</div>

    {{ right|safe }}

    <div class="mt-5 flex items-center justify-between gap-2">
      <div class="text-sm font-semibold">Extrahierter Text</div>
      <button id="reextractBtn" class="rounded-xl px-3 py-2 text-sm btn-outline card" type="button">
        Re-Extract (neu)
      </button>
    </div>

    <div class="muted text-xs mt-1" id="reextractStatus"></div>

    <textarea id="exText" class="w-full text-xs rounded-xl border border-slate-800 p-3 bg-slate-950/40 input mt-2"
      style="height:240px" readonly>{{extracted_text}}</textarea>

    <script>
      (function(){
        const btn = document.getElementById("reextractBtn");
        const st = document.getElementById("reextractStatus");
        const tx = document.getElementById("exText");

        async function doReextract(){
          st.textContent = "Re-Extract läuft…";
          btn.disabled = true;
          try{
            const res = await fetch("/api/reextract/{{token}}", {method:"POST"});
            const j = await res.json();
            if(!res.ok){
              st.textContent = "Fehler: " + (j.error || ("HTTP " + res.status));
              btn.disabled = false;
              return;
            }
            st.textContent = "Neu-Analyse gestartet. Öffne neuen Review…";
            setTimeout(()=>{ window.location.href = "/review/" + j.token + "/kdnr"; }, 250);
          }catch(e){
            st.textContent = "Netzwerk/Server-Fehler.";
            btn.disabled = false;
          }
        }

        btn?.addEventListener("click", doReextract);

        if((tx.value || "").trim().length < 40){
          st.textContent = "Hinweis: Text wirkt sehr kurz/kaputt → Re-Extract empfohlen.";
        }
      })();
    </script>
  </div>
</div>
"""

HTML_NOT_FOUND = r"""
<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card max-w-xl">
  <div class="text-xl font-semibold mb-2">Nicht gefunden</div>
  <div class="muted text-sm mb-4">
    Inhalt existiert nicht mehr (z.B. bereits abgelegt oder gelöscht).
  </div>
  <a class="rounded-xl px-4 py-2 font-semibold btn-primary inline-block" href="/">Zur Übersicht</a>
</div>
"""

HTML_CONFIRM = r"""
<div class="rounded-2xl border border-slate-800 p-4">
  <div class="text-lg font-semibold mb-1">Zusammenfassung</div>
  <div class="muted text-sm mb-4">Bitte prüfen. Du kannst jeden Punkt bearbeiten oder direkt final ablegen.</div>

  <div class="space-y-3">
    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Mandant/Firma</div>
      <div class="text-sm font-semibold break-all">{{w.tenant or "-"}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/kdnr">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Kundennummer</div>
      <div class="text-sm font-semibold break-all">{{w.kdnr}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/kdnr">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Name/Firma</div>
      <div class="text-sm font-semibold break-all">{{w.name}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/name">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Adresse</div>
      <div class="text-sm font-semibold break-all">{{w.addr}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/addr">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">PLZ/Ort</div>
      <div class="text-sm font-semibold break-all">{{w.plzort}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/plz">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Dokumenttyp</div>
      <div class="text-sm font-semibold break-all">{{w.doctype}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/doctype">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Dokumentdatum (optional)</div>
      <div class="text-sm font-semibold break-all">{{w.document_date or "-"}}</div>
      <a class="text-sm underline accentText" href="/review/{{token}}/docdate">Bearbeiten</a>
    </div>

    <div class="rounded-xl border border-slate-800 p-3">
      <div class="muted text-xs">Objektmodus</div>
      <div class="text-sm font-semibold break-all">
        {% if w.use_existing %}Bestandsobjekt{% else %}Neues Objekt{% endif %}
      </div>
      <div class="muted text-xs break-all">
        {% if w.use_existing %}{{w.use_existing}}{% else %}(wird neu erstellt){% endif %}
      </div>
      <a class="text-sm underline accentText" href="/review/{{token}}/kdnr">Bearbeiten</a>
    </div>

    <form method="post" class="pt-2 flex gap-2">
      <button class="rounded-xl px-4 py-2 font-semibold btn-primary" name="final" value="1">Alles korrekt → Ablage</button>
      <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/">Abbrechen</a>
    </form>
  </div>
</div>
"""

HTML_DONE = r"""
<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card">
  <div class="text-2xl font-bold mb-2">Fertig</div>
  <div class="muted text-sm mb-4">Zusammenfassung der Ablage</div>

  <div class="grid md:grid-cols-2 gap-4">
    <div class="rounded-xl border border-slate-800 p-4">
      <div class="text-sm font-semibold mb-2">Bestätigte Daten</div>
      <div class="text-sm">Mandant/Firma: <span class="font-semibold">{{tenant or "-"}}</span></div>
      <div class="text-sm">Kundennummer: <span class="font-semibold">{{kdnr}}</span></div>
      <div class="text-sm">Name/Firma: <span class="font-semibold">{{name}}</span></div>
      <div class="text-sm">Adresse: <span class="font-semibold">{{addr}}</span></div>
      <div class="text-sm">PLZ/Ort: <span class="font-semibold">{{plzort}}</span></div>
      <div class="text-sm mt-2">Objekt: <span class="font-semibold">{{objmode}}</span></div>
      <div class="text-sm">Dokumenttyp: <span class="font-semibold">{{doctype}}</span></div>
      <div class="text-sm">Dokumentdatum: <span class="font-semibold">{{document_date or "-"}}</span></div>
      <div class="text-sm mt-3">
        <span class="muted text-xs">Kundenstatus</span><br>
        <span class="font-semibold">{{customer_status}}</span>
      </div>
    </div>

    <div class="rounded-xl border border-slate-800 p-4">
      <div class="text-sm font-semibold mb-2">Ablage-Ergebnis</div>
      <div class="muted text-xs">Ziel-Ordner</div>
      <div class="text-sm break-all accentText">{{folder}}</div>

      <div class="muted text-xs mt-3">Datei-Pfad</div>
      <div class="text-sm break-all accentText">{{final_path}}</div>

      <div class="mt-4 flex flex-wrap gap-2">
        <a class="rounded-xl px-4 py-2 font-semibold btn-primary" href="/">Zur Übersicht</a>
        <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/open?fp={{fp_b64}}" target="_blank">Datei öffnen</a>
        <button class="rounded-xl px-4 py-2 font-semibold btn-outline card" type="button" onclick="navigator.clipboard.writeText('{{final_path}}')">Pfad kopieren</button>
      </div>
    </div>
  </div>
</div>
"""

HTML_ASSISTANT = r"""
<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
  <div class="text-lg font-semibold mb-1">Assistant (MVP)</div>
  <div class="muted text-sm mb-4">
    Suche über indexierte Dokumente. Sichtbar: Kundenablage (Eingang bleibt im Hintergrund).
  </div>

  <form method="get" class="flex flex-col md:flex-row gap-2 mb-4">
    <input class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="q"
      value="{{q}}" placeholder="z.B. wilhelmstr aufmaß bad angebot bohrmaschine" />
    <input class="w-full md:w-40 rounded-xl bg-slate-800 border border-slate-700 p-2 input" name="kdnr"
      value="{{kdnr}}" placeholder="Kdnr (optional)" />
    <button class="rounded-xl px-4 py-2 font-semibold btn-primary md:w-40" type="submit">Suchen</button>
  </form>

  {% if q %}
    <div class="muted text-xs mb-3">Treffer: {{results|length}}</div>
  {% endif %}

  {% if results %}
    <div class="space-y-2">
      {% for r in results %}
        <div class="rounded-xl border border-slate-800 p-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-sm font-semibold break-all">{{r.file_name}}</div>
              <div class="muted text-xs break-all">{{r.file_path}}</div>
              <div class="muted text-xs mt-1">
                Kdnr: <span class="font-semibold">{{r.kdnr or "-"}}</span> •
                Typ: <span class="font-semibold">{{r.doctype or "-"}}</span> •
                Datum: <span class="font-semibold">{{r.doc_date or "-"}}</span> •
                Versionen: <span class="font-semibold">{{r.version_count or 0}}</span>
              </div>
            </div>
            <div class="flex flex-col gap-2">
              {% if r.file_path %}
                <a class="rounded-xl px-3 py-2 text-sm btn-outline card" href="/open?fp={{r.fp_b64}}" target="_blank">Öffnen</a>
              {% endif %}
              {% if r.file_path %}
                <button class="rounded-xl px-3 py-2 text-sm btn-outline card" type="button"
                  onclick="navigator.clipboard.writeText('{{r.file_path}}')">Pfad kopieren</button>
              {% endif %}
            </div>
          </div>
          {% if r.preview %}
            <div class="mt-2 text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-2 bg-slate-950/40">{{r.preview}}</div>
          {% endif %}
        </div>
      {% endfor %}
    </div>
  {% elif q %}
    <div class="muted text-sm">Keine Treffer.</div>
  {% endif %}
</div>
"""


# ============================================================
# Rendering helpers
# ============================================================
def _render_review(token: str, right_html: str):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    filename = p.get("filename", "")
    used_ocr = bool(p.get("used_ocr", False))
    preview = p.get("preview", "")
    extracted_text = p.get("extracted_text", "")
    ext = Path(filename).suffix.lower()
    is_pdf = ext == ".pdf"
    is_text = ext == ".txt"

    w = _wizard_get(p)
    predicted = _predict_filename(w, p.get("doctype_suggested", "SONSTIGES"))

    return _render_base(
        render_template_string(
            HTML_REVIEW_SHELL,
            token=token,
            filename=filename,
            used_ocr=used_ocr,
            preview=preview,
            extracted_text=extracted_text,
            is_pdf=is_pdf,
            is_text=is_text,
            predicted_name=predicted,
            right=right_html,
        ),
        active_tab="upload",
    )


def _step_form(
    token: str,
    title: str,
    subtitle: str,
    field_name: str,
    current_value: str,
    suggestions: list,
    error: str = "",
    extra_html: str = "",
    show_scores: bool = False,
    ranked: list = None,
    next_label: str = "Weiter",
    placeholder: str = "",
):
    sug_buttons = ""

    if show_scores and ranked:
        for num, score in (ranked or [])[:8]:
            num_esc = str(num).replace('"', "&quot;")
            sug_buttons += f"""
              <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl"
                data-fill="{num_esc}">
                <div class="flex items-center justify-between">
                  <div class="font-semibold">{num}</div>
                  <div class="muted text-xs">Score {score}</div>
                </div>
              </button>
            """
    else:
        for s in (suggestions or [])[:8]:
            s_esc = str(s).replace('"', "&quot;")
            sug_buttons += f"""
              <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl"
                data-fill="{s_esc}">
                {s}
              </button>
            """

    err_html = _card_error(error) if error else ""

    right = f"""
      <form method="post" class="space-y-4" autocomplete="off">
        <div>
          <div class="text-lg font-semibold mb-1">{title}</div>
          <div class="muted text-sm">{subtitle}</div>
        </div>

        <div>
          <label class="muted text-xs">Eingabe (direkt tippen)</label>
          <input id="mainInput" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input"
            name="{field_name}" placeholder="{placeholder or title}" value="{(current_value or "").replace('"', "&quot;")}">
        </div>

        <div>
          <div class="muted text-xs mb-2">Vorschläge (Klick füllt das Feld)</div>
          <div class="grid gap-2">
            {sug_buttons if sug_buttons else '<div class="muted text-sm">Keine Vorschläge erkannt.</div>'}
          </div>
        </div>

        {extra_html}
        {err_html}

        <div class="pt-2 flex gap-2">
          <button class="rounded-xl px-4 py-2 font-semibold btn-primary" name="next" value="1">{next_label}</button>
          <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/">Abbrechen</a>
        </div>
      </form>

      <script>
      (function(){{
        const input = document.getElementById("mainInput");
        document.querySelectorAll("[data-fill]").forEach(btn => {{
          btn.addEventListener("click", () => {{
            input.value = btn.getAttribute("data-fill") || "";
            input.focus();
          }});
        }});
      }})();
      </script>
    """
    return _render_review(token, right)


# ============================================================
# Auth routes
# ============================================================
@APP.route("/login", methods=["GET", "POST"])
def login():
    if rbac_verify_user is None:
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
                _audit("login", target=u, meta={"roles": roles})
                return redirect(nxt or "/")
            error = "Login fehlgeschlagen."
    return render_template_string(HTML_LOGIN, error=error)


@APP.route("/logout")
def logout():
    if rbac_verify_user is None:
        return redirect(url_for("index"))
    if _logged_in():
        _audit("logout", target=_current_user(), meta={})
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# API
# ============================================================
@APP.route("/api/progress/<token>")
def api_progress(token):
    if not _logged_in():
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


@APP.route("/api/reextract/<token>", methods=["POST"])
def api_reextract(token):
    if not _logged_in():
        return jsonify(error="unauthorized"), 401
    p = read_pending(token)
    if not p:
        return jsonify(error="not_found"), 404

    tenant_id = _norm_tenant(str(p.get("tenant_id") or p.get("tenant") or ""))
    doc_id = str(p.get("doc_id") or token)
    tried_path = str(p.get("path", "") or "")

    if callable(resolve_source_path):
        src = resolve_source_path(token, p, tenant_id=tenant_id)
    else:
        fallback = Path(tried_path) if tried_path else None
        src = (
            fallback
            if fallback and fallback.exists() and _is_allowed_path(fallback)
            else None
        )

    if src is None:
        meta = {
            "token": token,
            "doc_id": doc_id,
            "tried_path": tried_path,
            "hint": "Source file not found under allowlisted roots; check versions.file_path or re-upload.",
        }
        _audit(
            "reextract_failed",
            target=token,
            meta={**meta, "old_token": token, "reason": "source_not_found"},
        )
        return jsonify(error="source_not_found", meta=meta), 404

    try:
        delete_pending(token)
    except Exception:
        pass

    try:
        new_token = analyze_to_pending(src)
    except Exception as e:
        _audit(
            "reextract_failed",
            target=token,
            meta={
                "old_token": token,
                "doc_id": doc_id,
                "resolved_path": str(src),
                "reason": "analyze_start_failed",
                "detail": str(e),
            },
        )
        return jsonify(error="analyze_start_failed"), 500

    _audit(
        "reextract_ok",
        target=str(src),
        meta={
            "old_token": token,
            "new_token": new_token,
            "doc_id": doc_id,
            "resolved_path": str(src),
        },
    )
    return jsonify(token=new_token, old_token=token)


@APP.route("/api/index_fullscan", methods=["POST"])
def api_index_fullscan():
    if not _logged_in():
        return jsonify(error="unauthorized"), 401
    if not _has_role("ADMIN") and rbac_verify_user is not None:
        return jsonify(error="forbidden"), 403
    if not callable(index_run_full):
        return jsonify(error="not_available"), 400

    try:
        res = index_run_full()
        _audit("index_fullscan", target=str(BASE_PATH), meta=res)
        return jsonify(ok=True, **(res or {}))
    except Exception as e:
        return jsonify(error=str(e)), 500


# ============================================================
# Main routes
# ============================================================
@APP.route("/")
def index():
    if not _logged_in():
        return redirect(url_for("login", next="/"))

    items_meta = list_pending()
    items = [x.get("_token") for x in items_meta if x.get("_token")]
    meta = {}
    for it in items_meta:
        t = it.get("_token")
        if not t:
            continue
        meta[t] = {
            "filename": it.get("filename", ""),
            "progress": float(it.get("progress", 0.0) or 0.0),
            "progress_phase": it.get("progress_phase", ""),
        }

    admin_tools = bool(_has_role("ADMIN")) or (rbac_verify_user is None)
    _audit("view_index", target="", meta={})
    return _render_base(
        render_template_string(
            HTML_INDEX, items=items, meta=meta, admin_tools=admin_tools
        ),
        active_tab="upload",
    )


@APP.route("/upload", methods=["POST"])
def upload():
    if not _logged_in():
        return jsonify(error="unauthorized"), 401

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="no_file"), 400

    tenant_raw = (request.form.get("tenant") or "").strip()
    tenant, terr = _tenant_or_error(tenant_raw)
    if terr:
        return jsonify(error=terr), 400

    filename = _safe_filename(f.filename)
    if not _is_allowed_ext(filename):
        return jsonify(error="unsupported"), 400

    # Eingang tenant-spezifisch
    tenant_in = EINGANG / tenant
    tenant_in.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = tenant_in / f"{ts}__{filename}"
    if dest.exists():
        dest = tenant_in / f"{ts}_{int(time.time())}__{filename}"

    f.save(dest)

    token = analyze_to_pending(dest)

    # tenant festnageln in Pending/Wizard
    try:
        p = read_pending(token) or {}
        p["tenant"] = tenant
        w = _wizard_get(p)
        w["tenant"] = tenant
        p["wizard"] = w
        write_pending(token, p)
    except Exception:
        pass

    _audit(
        "upload",
        target=str(dest),
        meta={"token": token, "filename": filename, "tenant": tenant},
    )
    return jsonify(token=token, tenant=tenant)


@APP.route("/review/<token>/delete", methods=["POST"])
def review_delete(token):
    if not _logged_in():
        return redirect(url_for("login", next="/"))

    p = read_pending(token)
    if p:
        src = Path(p.get("path", "") or "")
        try:
            delete_pending(token)
        except Exception:
            pass
        _audit("pending_delete", target=token, meta={"path": str(src)})
    return redirect(url_for("index"))


@APP.route("/file/<token>")
def file_preview(token):
    if not _logged_in():
        abort(401)
    p = read_pending(token)
    if not p:
        abort(404)
    file_path = Path(p.get("path", ""))
    if not file_path.exists():
        abort(404)
    if not _is_allowed_path(file_path):
        abort(403)
    _audit("open_pending_file", target=str(file_path), meta={"token": token})
    return send_file(file_path, as_attachment=False)


@APP.route("/open")
def open_any_file():
    if not _logged_in():
        abort(401)
    fp_b64 = (request.args.get("fp") or "").strip()
    if not fp_b64:
        abort(400)
    try:
        fp = Path(_unb64(fp_b64))
    except Exception:
        abort(400)
    if not fp.exists():
        abort(404)
    if not _is_allowed_path(fp):
        abort(403)
    _audit("open_file", target=str(fp), meta={})
    return send_file(fp, as_attachment=False)


@APP.route("/done/<token>")
def done_view(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/done/{token}"))
    d = read_done(token)
    if not d:
        return _render_base(HTML_NOT_FOUND)

    html = render_template_string(
        HTML_DONE,
        tenant=d.get("tenant", ""),
        kdnr=d.get("kdnr", ""),
        name=d.get("name", ""),
        addr=d.get("addr", ""),
        plzort=d.get("plzort", ""),
        objmode=d.get("objmode", ""),
        doctype=d.get("doctype", ""),
        folder=d.get("folder", ""),
        final_path=d.get("final_path", ""),
        created_new=bool(d.get("created_new", False)),
        customer_status=d.get("customer_status", ""),
        document_date=d.get("document_date", d.get("doc_date", "")),
        fp_b64=_b64(d.get("final_path", "")),
    )
    _audit("view_done", target=str(d.get("final_path", "")), meta={"token": token})
    return _render_base(html, active_tab="upload")


@APP.route("/health")
def health():
    return jsonify(ok=True, ts=time.time(), app="kundenablage_upload")


# ============================================================
# Review flow:
# kdnr -> name -> addr -> plz -> doctype -> docdate -> confirm -> archive
# ============================================================
def _build_object_picker(existing_objs: list, w_local: dict) -> str:
    items = ""
    for o in (existing_objs or [])[:12]:
        folder = o.get("folder", "")
        addr = o.get("addr", "")
        plzort = o.get("plzort", "")
        path_esc = (o.get("path", "") or "").replace('"', "&quot;")
        items += f"""
          <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl" data-objpath="{path_esc}">
            <div class="text-sm font-semibold">{folder}</div>
            <div class="muted text-xs">{addr} • {plzort}</div>
          </button>
        """

    chosen = "Neues Objekt"
    if w_local.get("use_existing"):
        try:
            chosen = Path(w_local.get("use_existing")).name
        except Exception:
            chosen = "Bestehendes Objekt"

    return f"""
      {_card_info("Bestandskunde erkannt. Optional Objekt wählen, um doppelte Ordner zu vermeiden.")}
      <div class="rounded-xl border border-slate-800 p-3 mt-3">
        <div class="text-sm font-semibold mb-2">Bestands-Objekt (optional)</div>

        <input type="hidden" id="objInput" name="use_existing" value="{(w_local.get("use_existing") or "").replace('"', "&quot;")}">
        <input type="hidden" name="confirm_kdnr" value="1">

        <label class="flex items-center gap-2 text-sm mb-3">
          <input type="checkbox" name="adopt_existing" value="1" {"checked" if w_local.get("adopt_existing", True) else ""}>
          <span>Bestandsdaten (Name/Adresse/PLZ) übernehmen (wenn Objekt gewählt wird)</span>
        </label>

        <div class="grid gap-2">
          <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl" data-objpath="">
            Neues Objekt anlegen
          </button>
          {items}
        </div>
        <div class="muted text-xs mt-2">Aktuell gewählt: <span class="font-semibold">{chosen}</span></div>
      </div>

      <script>
      (function(){{
        const objInput = document.getElementById("objInput");
        document.querySelectorAll("[data-objpath]").forEach(btn => {{
          btn.addEventListener("click", () => {{
            objInput.value = btn.getAttribute("data-objpath") || "";
          }});
        }});
      }})();
      </script>
    """


@APP.route("/review/<token>/kdnr", methods=["GET", "POST"])
def review_kdnr(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/kdnr"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    if p.get("status") == "ANALYZING":
        return _render_review(
            token,
            _card_info(
                "Analyse läuft noch… bitte kurz warten oder zurück zur Übersicht."
            ),
        )

    w = _wizard_get(p)

    # Ensure tenant is present from pending/upload
    if not w.get("tenant"):
        w["tenant"] = p.get("tenant", "") or _norm_tenant(TENANT_DEFAULT)

    ranked = p.get("kdnr_ranked") or []
    suggestions = [x[0] for x in ranked[:8]] if ranked else []

    if request.method == "POST":
        val = normalize_component(request.form.get("kdnr", "") or "")
        confirm_kdnr = (request.form.get("confirm_kdnr") or "").strip() == "1"
        chosen_obj_path = (request.form.get("use_existing") or "").strip()
        adopt_existing = (request.form.get("adopt_existing") or "").strip() == "1"

        # Tenant check (hard)
        tenant, terr = _tenant_or_error(w.get("tenant") or p.get("tenant") or "")
        if terr:
            return _render_base(
                _card_error(
                    "Mandant/Firma fehlt oder ist nicht erlaubt (Upload). Bitte zurück und erneut hochladen."
                )
            )

        w["tenant"] = tenant
        p["tenant"] = tenant

        if not val:
            _wizard_save(token, p, w)
            return _step_form(
                token=token,
                title="1) Kundennummer",
                subtitle="Direkt tippen oder Vorschlag anklicken. Weiter bestätigt.",
                field_name="kdnr",
                current_value=w.get("kdnr", ""),
                suggestions=suggestions,
                ranked=ranked,
                show_scores=True,
                error="Bitte Kundennummer eingeben oder Vorschlag anklicken.",
            )

        # Kdnr speichern
        w["kdnr"] = val
        w["adopt_existing"] = bool(adopt_existing)

        existing = (
            find_existing_customer_folders(BASE_PATH, val)
            if find_existing_customer_folders
            else []
        )
        w["customer_status"] = "BESTAND" if existing else "NEU"

        objs = []
        for f in existing:
            fields = parse_folder_fields(f.name) if parse_folder_fields else {}
            objs.append(
                {
                    "folder": f.name,
                    "path": str(f),
                    "name": fields.get("name", ""),
                    "addr": fields.get("addr", ""),
                    "plzort": fields.get("plzort", ""),
                }
            )
        p["existing_objects"] = objs

        # Phase 1: Bestandskunde erkannt -> Picker anzeigen und NICHT weiterleiten
        if existing and not confirm_kdnr:
            # best-effort Vorauswahl
            if (
                best_match_object_folder
                and parse_folder_fields
                and not w.get("use_existing")
            ):
                try:
                    best_path, best_score = best_match_object_folder(
                        existing, w.get("addr", ""), w.get("plzort", "")
                    )
                except Exception:
                    best_path, best_score = (existing[0] if existing else None), 0.0
                if best_path is None and existing:
                    best_path, best_score = existing[0], 0.0
                if best_path is not None:
                    bf = parse_folder_fields(best_path.name)
                    p["best_existing"] = {
                        "folder": best_path.name,
                        "path": str(best_path),
                        "name": bf.get("name", ""),
                        "addr": bf.get("addr", ""),
                        "plzort": bf.get("plzort", ""),
                        "score": best_score,
                    }
                    w["use_existing"] = str(best_path)

            if detect_object_duplicates_for_kdnr is not None:
                try:
                    dupes = detect_object_duplicates_for_kdnr(val, threshold=0.93)
                    p["object_dupes_suggested"] = dupes or []
                except Exception:
                    p["object_dupes_suggested"] = []

            _wizard_save(token, p, w)
            _audit(
                "review_set_kdnr_phase1",
                target=token,
                meta={"tenant": tenant, "kdnr": w["kdnr"], "existing": len(existing)},
            )

            extra = ""
            dupes = p.get("object_dupes_suggested") or []
            if dupes:
                extra += _card_warn(
                    f"⚠️ Mögliche Doppel-Objekte gefunden: {len(dupes)}. Admin sollte später mergen/prüfen."
                )

            extra += _build_object_picker(p.get("existing_objects") or [], w)

            prefill = w.get("kdnr") or (suggestions[0] if suggestions else "")
            return _step_form(
                token=token,
                title="1) Kundennummer",
                subtitle="Bestandskunde erkannt. Objekt optional wählen, dann Weiter.",
                field_name="kdnr",
                current_value=prefill,
                suggestions=suggestions,
                ranked=ranked,
                show_scores=True,
                extra_html=extra,
                next_label="Weiter",
            )

        # Phase 2: bestätigt -> use_existing übernehmen und optional Bestandsdaten ziehen
        w["use_existing"] = chosen_obj_path

        if w.get("use_existing") and w.get("adopt_existing") and parse_folder_fields:
            try:
                bf = parse_folder_fields(Path(w["use_existing"]).name)
                if not w.get("name") and bf.get("name"):
                    w["name"] = bf.get("name")
                if not w.get("addr") and bf.get("addr"):
                    w["addr"] = bf.get("addr")
                if not w.get("plzort") and bf.get("plzort"):
                    w["plzort"] = bf.get("plzort")
            except Exception:
                pass

        if detect_object_duplicates_for_kdnr is not None:
            try:
                dupes = detect_object_duplicates_for_kdnr(val, threshold=0.93)
                p["object_dupes_suggested"] = dupes or []
            except Exception:
                p["object_dupes_suggested"] = []

        _wizard_save(token, p, w)
        _audit(
            "review_set_kdnr",
            target=token,
            meta={
                "tenant": tenant,
                "kdnr": w["kdnr"],
                "customer_status": w["customer_status"],
            },
        )
        return redirect(url_for("review_name", token=token))

    # GET
    _wizard_save(token, p, w)
    prefill = w.get("kdnr") or (suggestions[0] if suggestions else "")
    extra = ""
    if w.get("kdnr"):
        existing = p.get("existing_objects") or []
        if existing:
            extra += _build_object_picker(existing, w)
    return _step_form(
        token=token,
        title="1) Kundennummer",
        subtitle="Direkt tippen oder Vorschlag anklicken. Weiter bestätigt.",
        field_name="kdnr",
        current_value=prefill,
        suggestions=suggestions,
        ranked=ranked,
        show_scores=True,
        extra_html=extra,
    )


@APP.route("/review/<token>/name", methods=["GET", "POST"])
def review_name(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/name"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)
    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggestions = (p.get("name_suggestions") or ["Kunde"])[:8]
    if w.get("name"):
        suggestions = [w.get("name")] + [s for s in suggestions if s != w.get("name")]

    if request.method == "POST":
        val = normalize_component(request.form.get("name", "") or "")
        if not val:
            return _step_form(
                token=token,
                title="2) Name / Firma",
                subtitle="Wenn es stimmt: Weiter.",
                field_name="name",
                current_value=w.get("name", ""),
                suggestions=suggestions,
                error="Bitte Name/Firma eingeben oder Vorschlag anklicken.",
            )
        w["name"] = val
        _wizard_save(token, p, w)
        _audit("review_set_name", target=token, meta={"name": w["name"]})
        return redirect(url_for("review_addr", token=token))

    prefill = w.get("name") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="2) Name / Firma",
        subtitle="Wenn es stimmt: Weiter.",
        field_name="name",
        current_value=prefill,
        suggestions=suggestions,
    )


@APP.route("/review/<token>/addr", methods=["GET", "POST"])
def review_addr(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/addr"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)
    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggestions = (p.get("addr_suggestions") or [])[:8]
    if w.get("addr"):
        suggestions = [w.get("addr")] + [s for s in suggestions if s != w.get("addr")]

    hint = ""
    if not suggestions:
        hint = _card_info(
            "Adresse-Vorschläge leer? Straße + Hausnummer manuell eintragen (z.B. „Treskowallee 211“)."
        )

    if request.method == "POST":
        val = normalize_component(request.form.get("addr", "") or "")
        if not val:
            return _step_form(
                token=token,
                title="3) Adresse (Straße + Nr)",
                subtitle="Wenn es stimmt: Weiter.",
                field_name="addr",
                current_value=w.get("addr", ""),
                suggestions=suggestions,
                error="Bitte Adresse eingeben oder Vorschlag anklicken.",
                extra_html=hint,
            )
        w["addr"] = val
        _wizard_save(token, p, w)
        _audit("review_set_addr", target=token, meta={"addr": w["addr"]})
        return redirect(url_for("review_plz", token=token))

    prefill = w.get("addr") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="3) Adresse (Straße + Nr)",
        subtitle="Wenn es stimmt: Weiter.",
        field_name="addr",
        current_value=prefill,
        suggestions=suggestions,
        extra_html=hint,
    )


@APP.route("/review/<token>/plz", methods=["GET", "POST"])
def review_plz(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/plz"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)
    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggestions = (p.get("plzort_suggestions") or ["PLZ Ort"])[:8]
    if w.get("plzort"):
        suggestions = [w.get("plzort")] + [
            s for s in suggestions if s != w.get("plzort")
        ]

    if request.method == "POST":
        val = normalize_component(request.form.get("plzort", "") or "")
        if not val:
            return _step_form(
                token=token,
                title="4) PLZ + Ort",
                subtitle="Wenn es stimmt: Weiter.",
                field_name="plzort",
                current_value=w.get("plzort", ""),
                suggestions=suggestions,
                error="Bitte PLZ/Ort eingeben oder Vorschlag anklicken.",
            )
        w["plzort"] = val
        _wizard_save(token, p, w)
        _audit("review_set_plzort", target=token, meta={"plzort": w["plzort"]})
        return redirect(url_for("review_doctype", token=token))

    prefill = w.get("plzort") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="4) PLZ + Ort",
        subtitle="Wenn es stimmt: Weiter.",
        field_name="plzort",
        current_value=prefill,
        suggestions=suggestions,
    )


@APP.route("/review/<token>/doctype", methods=["GET", "POST"])
def review_doctype(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/doctype"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)
    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggested = (p.get("doctype_suggested") or "SONSTIGES").upper()
    cur = (w.get("doctype") or suggested).upper()
    if cur not in DOCTYPE_CHOICES:
        cur = "SONSTIGES"

    if request.method == "POST":
        dt = (request.form.get("doctype") or "").strip().upper()
        if dt not in DOCTYPE_CHOICES:
            dt = "SONSTIGES"
        w["doctype"] = dt
        _wizard_save(token, p, w)
        _audit(
            "review_set_doctype",
            target=token,
            meta={"doctype": dt, "suggested": suggested},
        )
        return redirect(url_for("review_docdate", token=token))

    opts = ""
    for d in DOCTYPE_CHOICES:
        checked = "checked" if d == cur else ""
        badge = ""
        if d == suggested:
            badge = '<span class="muted text-[11px] ml-2">(Vorschlag)</span>'
        opts += f"""
          <label class="flex items-center gap-2 pickbtn px-3 py-2 rounded-xl cursor-pointer">
            <input type="radio" name="doctype" value="{d}" {checked}>
            <span class="font-semibold">{d}</span>
            {badge}
          </label>
        """

    right = f"""
      <form method="post" class="space-y-4">
        <div>
          <div class="text-lg font-semibold mb-1">5) Dokumenttyp</div>
          <div class="muted text-sm">KI macht nur Vorschlag. Du entscheidest.</div>
        </div>

        <div class="grid gap-2">
          {opts}
        </div>

        <div class="pt-2 flex gap-2">
          <button class="rounded-xl px-4 py-2 font-semibold btn-primary" type="submit">Weiter</button>
          <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/">Abbrechen</a>
        </div>
      </form>
    """
    return _render_review(token, right)


@APP.route("/review/<token>/docdate", methods=["GET", "POST"])
def review_docdate(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/docdate"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)
    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggested_raw = (p.get("doc_date_suggested") or "").strip()
    candidates = p.get("doc_date_candidates") or []

    suggestions: List[str] = []
    if suggested_raw:
        norm = parse_excel_like_date(suggested_raw)
        if norm:
            suggestions.append(norm)

    for c in candidates:
        d_raw = (c.get("date") or "").strip()
        norm = parse_excel_like_date(d_raw)
        if norm and norm not in suggestions:
            suggestions.append(norm)

    user_saved_norm = parse_excel_like_date(w.get("document_date", ""))
    if user_saved_norm and user_saved_norm not in suggestions:
        suggestions.insert(0, user_saved_norm)

    hint = _card_info(
        "Dokumentdatum ist OPTIONAL. Leer lassen ist erlaubt. "
        "Wenn gesetzt: z.B. 2025-10-24 oder 24.10.2025 (optional mit Uhrzeit)."
    )

    if request.method == "POST":
        raw = (request.form.get("document_date") or "").strip()

        # OPTIONAL: leeres Datum zulassen
        if not raw:
            w["document_date"] = ""
            _wizard_save(token, p, w)
            _audit("review_set_docdate", target=token, meta={"doc_date": ""})
            return redirect(url_for("review_confirm", token=token))

        norm = parse_excel_like_date(raw)
        if not norm:
            return _step_form(
                token=token,
                title="6) Dokumentdatum (optional)",
                subtitle="Akzeptiert Excel-Formate. Wird gespeichert als YYYY-MM-DD. Leer ist erlaubt.",
                field_name="document_date",
                current_value=w.get("document_date", "")
                or (suggestions[0] if suggestions else ""),
                suggestions=suggestions,
                error="Ungültiges Datum. Beispiele: 2025-10-24 oder 24.10.2025 (optional mit Uhrzeit). Oder Feld leer lassen.",
                extra_html=hint,
                placeholder="z.B. 24.10.2025 oder leer",
            )

        w["document_date"] = norm
        _wizard_save(token, p, w)
        _audit(
            "review_set_docdate", target=token, meta={"doc_date": w["document_date"]}
        )
        return redirect(url_for("review_confirm", token=token))

    prefill = w.get("document_date") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="6) Dokumentdatum (optional)",
        subtitle="Akzeptiert Excel-Formate. Wird gespeichert als YYYY-MM-DD. Leer ist erlaubt.",
        field_name="document_date",
        current_value=prefill,
        suggestions=suggestions,
        extra_html=hint,
        placeholder="z.B. 24.10.2025 oder leer",
    )


@APP.route("/review/<token>/confirm", methods=["GET", "POST"])
def review_confirm(token):
    if not _logged_in():
        return redirect(url_for("login", next=f"/review/{token}/confirm"))

    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)
    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    if not w.get("doctype"):
        w["doctype"] = (p.get("doctype_suggested") or "SONSTIGES").upper()

    # doc_date remains optional: do NOT force-fill with today
    if w.get("document_date"):
        w["document_date"] = parse_excel_like_date(w.get("document_date")) or ""

    # Ensure tenant is valid
    tenant, terr = _tenant_or_error(w.get("tenant") or p.get("tenant") or "")
    if terr:
        return _render_base(
            _card_error(
                "Mandant/Firma fehlt oder ist nicht erlaubt. Bitte Upload erneut durchführen."
            )
        )
    w["tenant"] = tenant
    p["tenant"] = tenant

    _wizard_save(token, p, w)

    if request.method == "POST" and request.form.get("final") == "1":
        src = Path(p.get("path", ""))
        if not src.exists():
            _audit("archive_missing_src", target=str(src), meta={"token": token})
            return _render_base(
                _card_error(
                    "Datei im Eingang nicht gefunden (evtl. verschoben/gelöscht)."
                )
            )

        answers = {
            "tenant": tenant,  # NEW
            "kdnr": w.get("kdnr", ""),
            "use_existing": w.get("use_existing", ""),
            "name": w.get("name", "Kunde"),
            "addr": w.get("addr", "Adresse"),
            "plzort": w.get("plzort", "PLZ Ort"),
            "doctype": w.get("doctype", p.get("doctype_suggested", "SONSTIGES")),
            "document_date": w.get("document_date", ""),  # may be ""
        }

        try:
            folder, final_path, created_new = process_with_answers(src, answers)
        except Exception as e:
            _audit(
                "archive_error",
                target=str(src),
                meta={"error": str(e), "tenant": tenant},
            )
            return _render_base(_card_error(f"Ablage fehlgeschlagen: {e}"))

        done_payload = {
            "tenant": tenant,
            "kdnr": answers["kdnr"],
            "name": answers["name"],
            "addr": answers["addr"],
            "plzort": answers["plzort"],
            "doctype": answers.get("doctype", "SONSTIGES"),
            "document_date": answers.get("document_date", ""),
            "folder": str(folder),
            "final_path": str(final_path),
            "created_new": bool(created_new),
            "objmode": (
                "Bestehendes Objekt" if answers.get("use_existing") else "Neues Objekt"
            ),
            "customer_status": (
                w.get("customer_status")
                or ("BESTAND" if answers.get("use_existing") else "NEU")
            ),
        }
        write_done(token, done_payload)

        delete_pending(token)

        _audit(
            "archive_ok",
            target=str(final_path),
            meta={
                "tenant": tenant,
                "kdnr": answers["kdnr"],
                "doctype": done_payload["doctype"],
            },
        )
        return redirect(url_for("done_view", token=token))

    right = render_template_string(HTML_CONFIRM, token=token, w=w)
    return _render_review(token, right)


# ============================================================
# Assistant
# ============================================================
def _dedupe_assistant_results(rows: list) -> list:
    out = []
    seen = set()

    def key_for(path: str) -> str:
        try:
            p = Path(path)
            stem = p.stem
            stem2 = re.sub(r"_(\d{6})$", "", stem)
            return str(p.parent) + "/" + stem2.lower() + p.suffix.lower()
        except Exception:
            return (path or "").lower()

    for r in rows or []:
        fp = r.get("file_path") or r.get("current_path") or ""
        if not fp:
            continue

        if ASSISTANT_HIDE_EINGANG:
            try:
                if str(Path(fp).resolve()).startswith(str(EINGANG.resolve()) + os.sep):
                    continue
            except Exception:
                pass

        k = key_for(fp)
        if k in seen:
            continue
        seen.add(k)

        r2 = dict(r)
        r2["file_path"] = fp
        out.append(r2)
    return out


@APP.route("/assistant")
def assistant():
    if not _logged_in():
        return redirect(url_for("login", next="/assistant"))

    q = normalize_component(request.args.get("q", "") or "")
    kdnr = normalize_component(request.args.get("kdnr", "") or "")

    results = []
    if q:
        if assistant_search is None:
            return _render_base(
                _card_error("Assistant ist im Core noch nicht verfügbar."),
                active_tab="assistant",
            )
        try:
            role = _current_roles()[0] if _current_roles() else "ADMIN"
            try:
                raw = assistant_search(query=q, kdnr=kdnr, limit=50, role=role)
            except TypeError:
                raw = assistant_search(query=q, kdnr=kdnr, limit=50)

            raw = _dedupe_assistant_results(raw)
            for r in raw:
                fp = r.get("file_path", "")
                r["fp_b64"] = _b64(fp) if fp else ""
                results.append(r)
            _audit(
                "assistant_search", target=q, meta={"kdnr": kdnr, "hits": len(results)}
            )
        except Exception as e:
            return _render_base(
                _card_error(f"Assistant-Fehler: {e}"), active_tab="assistant"
            )

    html = render_template_string(HTML_ASSISTANT, q=q, kdnr=kdnr, results=results)
    return _render_base(html, active_tab="assistant")


# ============================================================
# Start
# ============================================================
if __name__ == "__main__":
    EINGANG.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BASE_PATH.mkdir(parents=True, exist_ok=True)

    if db_init is not None:
        db_init()
    _ensure_bootstrap_admin()

    print(f"http://127.0.0.1:{PORT}")
    APP.run(host="127.0.0.1", port=PORT, debug=False)
