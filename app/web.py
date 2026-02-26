#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KUKANILEA Systems — Enterprise UI / UX v4.4 (Restored & Optimized)
=============================================================
Restores the acclaimed overlay layout and original trademarked logo.
"""

from __future__ import annotations

import json
import os
import re
import time
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)

from app import core
from app.agents.orchestrator import answer as agent_answer
from app.agents.retrieval_fts import enqueue as rag_enqueue
from app.agents import AgentContext, CustomerAgent, SearchAgent
from app.agents.orchestrator import Orchestrator

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

# -------- Globals & Setup ----------
bp = Blueprint("web", __name__)

def _core_get(name: str, default=None):
    return getattr(core, name, default)

EINGANG: Path = _core_get("EINGANG")
BASE_PATH: Path = _core_get("BASE_PATH")
PENDING_DIR: Path = _core_get("PENDING_DIR")
DONE_DIR: Path = _core_get("DONE_DIR")
SUPPORTED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".txt"}

analyze_to_pending = _core_get("analyze_to_pending")
read_pending = _core_get("read_pending")
write_pending = _core_get("write_pending")
delete_pending = _core_get("delete_pending")
list_pending = _core_get("list_pending")
write_done = _core_get("write_done")
read_done = _core_get("read_done")
process_with_answers = _core_get("process_with_answers")
normalize_component = _core_get("normalize_component", lambda s: (s or "").strip())
db_init = _core_get("db_init")
assistant_search = _core_get("assistant_search")

DOCTYPE_CHOICES = ["RECHNUNG", "ANGEBOT", "LIEFERSCHEIN", "MAHNUNG", "SONSTIGES"]

# -------- Original Trademarked Logo ----------
SVG_LOGO = r"""
<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:100%; display:block;">
  <circle cx="50" cy="50" r="42" stroke="#D4AF37" stroke-width="6" stroke-dasharray="10 5" />
  <path d="M50 8C55 8 60 12 60 18C60 24 55 28 50 28C45 28 40 24 40 18C40 12 45 8 50 8Z" fill="#D4AF37" />
  <path d="M82 50C82 55 78 60 72 60C66 60 62 55 62 50C62 45 66 41 72 41C78 41 82 45 82 50Z" fill="#D4AF37" />
  <path d="M50 92C45 92 40 88 40 82C40 76 45 72 50 72C55 72 60 76 60 82C60 88 55 92 50 92Z" fill="#D4AF37" />
  <path d="M18 50C18 45 22 40 28 40C34 40 38 45 38 50C38 55 34 59 28 59C22 59 18 55 18 50Z" fill="#D4AF37" />
  <path d="M38 35V65M38 50L58 35M38 50L58 65" stroke="#1E3A8A" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

# -------- Base Template (Classic Shell) ----------
HTML_BASE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="csrf-token" content="{{ csrf_token() }}">
<link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='icons/app-icon.svg') }}">
<title>{{branding.app_name}} Enterprise Systems</title>
<script src="{{ url_for('static', filename='vendor/tailwindcss.min.js') }}"></script>
<script>
  const savedTheme = localStorage.getItem("ks_theme") || "light";
  if(savedTheme === "dark"){ document.documentElement.classList.add("dark"); }
</script>
<style>
  :root {
    --bg: #ffffff; --bg-elev: #f8fafc; --bg-panel: #ffffff; --border: #e2e8f0;
    --text: #0f172a; --muted: #64748b; --accent-500: #D4AF37; --accent-600: #B8860B;
    --navy: #1E3A8A; --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    --radius-lg: 12px; --radius-md: 8px; --nav-width: 260px;
  }
  .dark body {
    --bg: #0f172a; --bg-elev: #1e293b; --bg-panel: #1e293b; --border: #334155;
    --text: #f8fafc; --muted: #94a3b8; --shadow: 0 10px 15px -3px rgb(0 0 0 / 0.5);
  }
  * { box-sizing: border-box; }
  body { 
    background-color: var(--bg); color: var(--text); margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased; height: 100vh; overflow: hidden; width: 100vw;
  }
  .app-shell { display: flex; height: 100vh; width: 100vw; }
  .app-nav {
    width: var(--nav-width); background: var(--bg-elev); border-right: 1px solid var(--border);
    padding: 24px 16px; height: 100vh; display: flex; flex-direction: column; flex-shrink: 0;
  }
  .app-main { flex: 1; display: flex; flex-direction: column; background: var(--bg); min-width: 0; height: 100vh; }
  .app-topbar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0 32px; height: 64px; border-bottom: 1px solid var(--border); background: var(--bg-panel);
    flex-shrink: 0; width: 100%;
  }
  .app-content-scroll { flex: 1; overflow-y: auto; padding: 32px; width: 100%; }
  .app-content-container { max-width: 1200px; margin: 0 auto; width: 100%; }
  
  .nav-link {
    display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: var(--radius-md);
    color: var(--muted); text-decoration: none; transition: all 0.2s; font-size: 0.95rem; font-weight: 500;
  }
  .nav-link:active { transform: scale(0.97); }
  .nav-link:hover { background: rgba(0,0,0,0.03); color: var(--text); }
  .dark .nav-link:hover { background: rgba(255,255,255,0.05); }
  .nav-link.active { background: var(--navy); color: white; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.2); }
  
  .card { background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow); }
  .btn-primary { 
    background: var(--navy); color: white; border-radius: var(--radius-md); padding: 10px 20px; font-weight: 600; border: none; cursor: pointer; 
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  }
  .btn-primary:hover { filter: brightness(1.1); transform: translateY(-1px); }
  .btn-primary:active { transform: scale(0.96); }
  
  .btn-outline { 
    border: 1px solid var(--border); border-radius: var(--radius-md); padding: 8px 16px; background: transparent; color: var(--text); 
    cursor: pointer; text-decoration: none; font-size: 0.875rem; transition: all 0.2s; 
  }
  .btn-outline:hover { background: rgba(0,0,0,0.03); }
  
  .input { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 10px 14px; color: var(--text); width: 100%; }
  .badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; background: var(--bg-elev); border: 1px solid var(--border); color: var(--muted); font-weight: 600; }
  .logo-container { width: 44px; height: 44px; flex-shrink: 0; }
</style>
</head>
<body>
<main class="app-shell" role="main">
  <nav class="app-nav" aria-label="Hauptnavigation">
    <div style="display:flex; align-items:center; gap:14px; margin-bottom:40px; padding:0 8px;">
      <div class="logo-container" role="img" aria-label="KUKANILEA Logo">""" + SVG_LOGO + r"""</div>
      <div style="overflow:hidden; line-height:1.15;">
        <div style="font-weight:800; font-size:18px; color:var(--navy); text-transform:uppercase;">{{branding.app_name}}</div>
        <div style="font-size:9px; text-transform:uppercase; font-weight:700; color:var(--accent-600);">Enterprise Core</div>
      </div>
    </div>
    <div style="flex:1; display:flex; flex-direction:column; gap:4px;">
      <a class="nav-link {{'active' if active_tab=='upload' else ''}}" href="/" aria-current="{{'page' if active_tab=='upload' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
        Upload
      </a>
      <a class="nav-link {{'active' if active_tab=='tasks' else ''}}" href="/tasks" aria-current="{{'page' if active_tab=='tasks' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
        Aufgaben
      </a>
      <a class="nav-link {{'active' if active_tab=='time' else ''}}" href="/time" aria-current="{{'page' if active_tab=='time' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        Zeiterfassung
      </a>
      <a class="nav-link {{'active' if active_tab=='assistant' else ''}}" href="/assistant" aria-current="{{'page' if active_tab=='assistant' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>
        Assistent
      </a>
      <a class="nav-link {{'active' if active_tab=='chat' else ''}}" href="/chat" aria-current="{{'page' if active_tab=='chat' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>
        Chat
      </a>
      <a class="nav-link {{'active' if active_tab=='mail' else ''}}" href="/mail" aria-current="{{'page' if active_tab=='mail' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
        Postfach
      </a>
      {% if roles in ['DEV', 'ADMIN'] %}
      <div role="presentation" style="padding: 24px 12px 8px; font-size: 10px; font-weight: bold; text-transform: uppercase; color: var(--muted); opacity: 0.7;">Verwaltung</div>
      <a class="nav-link {{'active' if active_tab=='mesh' else ''}}" href="/admin/mesh" aria-current="{{'page' if active_tab=='mesh' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 16-5.16-5.16a2 2 0 0 0-2.82 0L3 21"/><circle cx="16" cy="7" r="4"/></svg>
        Mesh (Admin)
      </a>
      <a class="nav-link {{'active' if active_tab=='settings' else ''}}" href="/settings" aria-current="{{'page' if active_tab=='settings' else 'false'}}">
        <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/></svg>
        Einstellungen
      </a>
      {% endif %}
    </div>
    <footer style="margin-top:auto; padding-top:24px; border-top:1px dashed var(--border);">
      <div style="font-size:10px; font-weight:bold; color:var(--muted); margin-bottom:4px;">ABLAGE</div>
      <div style="font-size:12px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="{{ablage}}">{{ablage}}</div>
    </footer>
  </nav>
  <div class="app-main">
    <header class="app-topbar" aria-label="Anwendungs-Kopfzeile">
      <div style="display:flex; align-items:center; gap:16px;"><h2 style="font-size:14px; font-weight:bold; text-transform:uppercase; letter-spacing:0.1em;">{{ active_tab|capitalize }}</h2></div>
      <div style="display:flex; align-items:center; gap:16px;">
        <span class="badge" role="status">{{tenant}}</span><span class="badge" role="status">{{roles}}</span>
        <div style="height:32px; width:1px; background:var(--border);"></div>
        <button id="themeBtn" aria-label="Farbschema umschalten" style="padding:8px; background:transparent; border:none; cursor:pointer; color:var(--text);">
          <span class="dark:hidden"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg></span>
          <span class="hidden dark:inline"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg></span>
        </button>
        {% if user and user != '-' %}
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="text-align:right;"><div style="font-size:12px; font-weight:bold;">{{user}}</div><div style="font-size:10px; color:var(--muted);">{{profile.name}}</div></div>
          <a class="btn-outline" style="font-size:12px; padding:6px 12px;" href="/logout">Abmelden</a>
        </div>
        {% endif %}
      </div>
    </header>
    <section class="app-content-scroll" aria-label="Inhalt"><div class="app-content-container">{{ content|safe }}</div></section>
  </div>
</main>
<script>
(function(){
  const btnTheme = document.getElementById("themeBtn");
  function curTheme(){ return (localStorage.getItem("ks_theme") || "light"); }
  function applyTheme(t){
    if(t === "dark"){ document.documentElement.classList.add("dark"); }
    else { document.documentElement.classList.remove("dark"); }
    localStorage.setItem("ks_theme", t);
  }
  applyTheme(curTheme());
  btnTheme?.addEventListener("click", ()=>{ applyTheme(curTheme()==="dark"?"light":"dark"); window.location.reload(); });
})();
</script>
</body>
</html>"""

# -------- Login Template ----------
HTML_LOGIN = r"""
<div class="max-w-md mx-auto mt-20" id="bootSequence">
  <div class="card p-10 bg-slate-900 border-slate-800 shadow-2xl overflow-hidden relative">
    <div class="absolute top-0 left-0 w-full h-1 bg-slate-800">
        <div id="bootProgress" class="h-full bg-accent-500 transition-all duration-500" style="width: 0%"></div>
    </div>
    <div class="flex flex-col items-center justify-center py-10">
      <div class="mb-8" style="width:80px; height:80px;">""" + SVG_LOGO + r"""</div>
      <div class="text-center space-y-4 w-full">
        <div class="text-white font-mono text-xs tracking-widest uppercase opacity-50" id="bootPhase">Kernel Boot</div>
        <div class="h-4 flex items-center justify-center">
            <div class="flex gap-1" id="bootDots">
                <div class="w-1.5 h-1.5 rounded-full bg-accent-500 animate-bounce" style="animation-delay: 0s"></div>
                <div class="w-1.5 h-1.5 rounded-full bg-accent-500 animate-bounce" style="animation-delay: 0.2s"></div>
                <div class="w-1.5 h-1.5 rounded-full bg-accent-500 animate-bounce" style="animation-delay: 0.4s"></div>
            </div>
        </div>
        <div class="text-[10px] font-mono text-accent-400 bg-slate-800/50 p-3 rounded-lg border border-slate-700/50 break-all h-16 flex items-center justify-center" id="bootDetails">Loading...</div>
      </div>
    </div>
    <div class="mt-6 pt-6 border-t border-slate-800 text-center"><p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Enterprise Core Bootloader</p></div>
  </div>
</div>
<div class="max-w-md mx-auto mt-20 hidden" id="loginForm">
  <div class="card p-10 bg-white shadow-2xl">
    <div class="flex items-center gap-4 mb-8 justify-center">
      <div style="width:56px; height:56px;">""" + SVG_LOGO + r"""</div>
      <div style="line-height:1.15;">
        <div style="font-weight:800; font-size:24px; color:#1E3A8A; text-transform:uppercase;">KUKANILEA</div>
        <div style="font-size:10px; font-weight:700; color:#B8860B;">Enterprise Office</div>
      </div>
    </div>
    {% if error %}<div class="mb-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700 font-bold shadow-sm">{{ error }}</div>{% endif %}
    <form method="post" class="space-y-6">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <div class="space-y-1"><label class="muted text-[10px] font-bold uppercase tracking-widest px-1">Benutzername</label><input class="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm" name="username" required></div>
      <div class="space-y-1"><label class="muted text-[10px] font-bold uppercase tracking-widest px-1">Passwort</label><input class="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm" type="password" name="password" required></div>
      <div class="pt-2"><button class="w-full rounded-xl px-6 py-4 font-bold btn-primary text-lg" type="submit" style="background:#1E3A8A;">Login</button></div>
    </form>
  </div>
</div>
<script>
(function(){
    const boot = document.getElementById('bootSequence'), login = document.getElementById('loginForm'), phase = document.getElementById('bootPhase'), details = document.getElementById('bootDetails'), bar = document.getElementById('bootProgress');
    const pollStatus = async () => {
        try {
            const res = await fetch('/health'), data = await res.json();
            phase.textContent = data.state; details.textContent = data.details;
            if (data.state === 'BOOT') bar.style.width = '20%';
            if (data.state === 'INIT') bar.style.width = '60%';
            if (data.state === 'READY') {
                bar.style.width = '100%';
                setTimeout(() => { boot.classList.add('hidden'); login.classList.remove('hidden'); }, 800);
                return;
            }
            setTimeout(pollStatus, 500);
        } catch (e) { setTimeout(pollStatus, 1000); }
    };
    pollStatus();
})();
</script>
"""

# -------- Dashboard Template ----------
HTML_INDEX = r"""
<div class="space-y-10">
  <div class="card p-10 bg-white">
    <div class="flex items-center gap-4 mb-8">
      <div style="width:40px; height:40px;">""" + SVG_LOGO + r"""</div>
      <h1 class="text-2xl font-bold text-slate-900">Beleg-Zentrale</h1>
    </div>
    
    <div id="dropZone" class="relative group border-2 border-dashed border-slate-200 rounded-3xl p-12 text-center bg-slate-50/50 hover:bg-white hover:border-accent-500 transition-all cursor-pointer">
      <input type="file" id="file" class="absolute inset-0 opacity-0 cursor-pointer" multiple accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.txt">
      <div class="mb-6 flex justify-center">
        <div class="h-16 w-16 rounded-2xl bg-white shadow-sm flex items-center justify-center text-accent-600 border border-slate-100 group-hover:scale-110 transition-transform">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
        </div>
      </div>
      <div class="text-lg font-bold text-slate-900 mb-2">Dateien auswählen oder ablegen</div>
      <div class="muted text-sm font-medium">Max. 50MB pro Dokument</div>
    </div>

    <div id="stagingArea" class="mt-10 hidden space-y-6">
      <div class="flex items-center justify-between px-2">
        <div class="text-xs font-bold uppercase tracking-widest text-slate-500">Warteliste für Upload (<span id="fileCount">0</span>)</div>
        <button id="clearStaging" class="text-xs font-bold text-rose-600 hover:underline">Alle leeren</button>
      </div>
      <div id="fileList" class="grid gap-3 sm:grid-cols-2"></div>
      <div class="pt-4">
        <button id="startAnalysis" class="w-full btn-primary text-lg py-4 shadow-xl">ANALYSE STARTEN</button>
      </div>
    </div>

    <div id="progressArea" class="mt-10 hidden p-10 rounded-3xl bg-slate-900 text-white shadow-2xl relative overflow-hidden">
      <div class="relative z-10">
        <div class="flex justify-between items-end mb-6">
          <div>
            <div id="phase" class="text-xs font-bold uppercase tracking-widest text-accent-500 mb-1">Vorbereitung...</div>
            <div id="status" class="text-lg font-bold text-white">Analyse läuft...</div>
          </div>
          <div id="pLabel" class="text-3xl font-black text-white italic">0.0%</div>
        </div>
        <div class="h-3 w-full bg-white/10 rounded-full overflow-hidden border border-white/5">
          <div id="bar" class="h-full bg-accent-500 shadow-[0_0_20px_rgba(212,175,55,0.5)] transition-all duration-300" style="width: 0%"></div>
        </div>
      </div>
    </div>
  </div>

  <div class="space-y-6">
    <div class="flex items-center justify-between px-2">
      <h2 class="text-sm font-bold uppercase tracking-widest text-slate-500 italic">Warteschlange zur Prüfung</h2>
    </div>
    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {% for token in items %}
      {% set m = meta[token] %}
      <a href="/review/{{token}}/kdnr" class="card p-6 bg-white hover:border-navy transition-all group">
        <div class="flex items-center justify-between mb-4">
          <div class="h-10 w-10 rounded-xl bg-slate-50 flex items-center justify-center text-navy group-hover:bg-navy group-hover:text-white transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          </div>
          <span class="badge">{{ m.status }}</span>
        </div>
        <div class="text-sm font-bold text-slate-900 truncate mb-1">{{ m.filename }}</div>
        <div class="text-[10px] muted uppercase tracking-widest">{{ token[:8] }}...</div>
      </a>
      {% endfor %}
    </div>
  </div>

  <div class="space-y-6">
    <div class="flex items-center justify-between px-2">
      <h2 class="text-sm font-bold uppercase tracking-widest text-slate-500 italic">Verlauf der letzten 24h</h2>
    </div>
    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {% for r in recent %}
      <div class="card p-6 bg-white hover:border-accent-500 transition-colors cursor-default">
        <div class="flex items-start justify-between mb-4">
          <div class="h-10 w-10 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-400">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-tighter">{{ r.created_at[:10] }}</span>
        </div>
        <div class="text-sm font-bold text-slate-900 truncate mb-1" title="{{ r.file_name }}">{{ r.file_name }}</div>
        <div class="flex items-center gap-2">
          <span class="badge bg-slate-50 border-slate-100 text-[9px] uppercase">{{ r.doctype }}</span>
          <span class="badge bg-slate-50 border-slate-100 text-[9px] uppercase">KDNR: {{ r.kdnr }}</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
</div>

<script>
(function(){
  const fileInput = document.getElementById("file"), stagingArea = document.getElementById("stagingArea"), fileList = document.getElementById("fileList"), fileCount = document.getElementById("fileCount"), clearStaging = document.getElementById("clearStaging"), startBtn = document.getElementById("startAnalysis"), progressArea = document.getElementById("progressArea"), bar = document.getElementById("bar"), pLabel = document.getElementById("pLabel"), status = document.getElementById("status"), phase = document.getElementById("phase");
  let stagedFiles = [];
  const updateUI = () => {
    fileList.innerHTML = "";
    stagedFiles.forEach((f, i) => {
      const d = document.createElement("div");
      d.className = "flex items-center justify-between p-3 rounded-xl bg-white border border-slate-200 text-sm shadow-sm";
      d.innerHTML = `<div class="truncate font-medium">${f.name}</div><button class="text-rose-600 font-bold px-2 py-1 text-xs hover:bg-rose-50 rounded-lg transition-colors" onclick="window._rm(${i})">Entfernen</button>`;
      fileList.appendChild(d);
    });
    fileCount.textContent = stagedFiles.length;
    stagingArea.classList.toggle("hidden", stagedFiles.length === 0);
  };
  window._rm = (i) => { stagedFiles.splice(i, 1); updateUI(); };
  fileInput.addEventListener("change", () => { for(let f of fileInput.files) stagedFiles.push(f); fileInput.value = ""; updateUI(); });
  clearStaging.addEventListener("click", () => { stagedFiles = []; updateUI(); });
  
  let targetProgress = 0, displayProgress = 0;
  const smooth = () => {
    if (displayProgress < targetProgress) {
      displayProgress += Math.max(0.1, (targetProgress - displayProgress) * 0.1);
      if (displayProgress > targetProgress) displayProgress = targetProgress;
      bar.style.width = displayProgress + "%"; pLabel.textContent = displayProgress.toFixed(1) + "%";
    }
    requestAnimationFrame(smooth);
  };
  smooth();

  const poll = async (token, isLast) => {
    try {
      const res = await fetch("/api/progress/" + token), j = await res.json();
      if(isLast) { targetProgress = 35 + (j.progress || 0) * 0.65; phase.textContent = j.progress_phase || "Analyse..."; }
      if(j.status === "READY" || j.status === "ERROR"){ 
        if(isLast) { 
          targetProgress = 100; status.textContent = j.status === "READY" ? "Fertig!" : "Fehler.";
          setTimeout(() => { if(j.status === "READY") window.location.href = "/review/" + token + "/kdnr"; }, 1000);
        } return; 
      }
      setTimeout(() => poll(token, isLast), 800);
    } catch(e) { setTimeout(() => poll(token, isLast), 2000); }
  };

  startBtn.addEventListener("click", async () => {
    if(!stagedFiles.length) return;
    progressArea.classList.remove("hidden"); stagingArea.classList.add("hidden");
    targetProgress = 0; displayProgress = 0;
    const fd = new FormData(); stagedFiles.forEach(f => fd.append("file", f));
    const xhr = new XMLHttpRequest(); xhr.open("POST", "/upload", true);
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
    if(csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
    xhr.upload.onprogress = (ev) => { if(ev.lengthComputable){ targetProgress = (ev.loaded / ev.total) * 35; phase.textContent = "Übertragung..."; } };
    xhr.onload = () => {
      if(xhr.status === 200){
        try {
          const resp = JSON.parse(xhr.responseText);
          if(resp.tokens?.length) resp.tokens.forEach((t, i) => poll(t.token, i === resp.tokens.length - 1));
          else status.textContent = "Upload erfolgreich, aber keine Token erhalten.";
        } catch(e) {
          status.textContent = "Server-Antwort konnte nicht gelesen werden.";
        }
      } else {
        try {
          const resp = JSON.parse(xhr.responseText);
          status.textContent = "Fehler: " + (resp.message || resp.error || xhr.status);
        } catch(e) {
          status.textContent = "Server-Fehler " + xhr.status;
        }
        stagingArea.classList.remove("hidden");
      }
    };
    xhr.onerror = () => {
      status.innerHTML = '<div class="text-rose-400 font-bold mb-2">Netzwerkfehler oder Zeitüberschreitung.</div><div class="text-xs opacity-70">Der Server (Port 5051) ist eventuell überlastet oder die Datei ist zu groß. Bitte Seite neu laden und erneut versuchen.</div>';
      stagingArea.classList.remove("hidden");
    };
    xhr.ontimeout = () => {
      status.textContent = "Zeitüberschreitung beim Upload. Bitte Internetverbindung prüfen.";
      stagingArea.classList.remove("hidden");
    };
    xhr.timeout = 300000;
    xhr.send(fd);
  });
})();
</script>
"""

# -------- Review Template ----------
HTML_REVIEW_SPLIT = r"""
<div class="flex h-[calc(100vh-160px)] gap-8">
  <div class="flex-1 card overflow-hidden bg-slate-900 shadow-2xl relative border-none">
    {% if preview %}
      <div id="preview-placeholder" class="absolute inset-0 w-full h-full flex items-center justify-center bg-slate-900 z-0">
         <img src="data:image/png;base64,{{preview}}" class="max-w-full max-h-full rounded shadow-2xl opacity-60 blur-sm" alt="Vorschau wird geladen...">
      </div>
    {% endif %}

    {% if is_pdf %}
      <iframe src="/file/{{token}}" class="w-full h-full border-none relative z-10 bg-transparent" title="PDF Vorschau" onload="document.getElementById('preview-placeholder')?.classList.add('hidden')"></iframe>
    {% elif preview %}
      <div class="w-full h-full p-10 flex items-center justify-center relative z-10">
        <img src="data:image/png;base64,{{preview}}" class="max-w-full max-h-full rounded shadow-2xl" alt="Beleg Vorschau">
      </div>
    {% else %}
      <div class="w-full h-full flex flex-col items-center justify-center text-white/20">
        <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span class="mt-4 font-bold uppercase tracking-widest text-xs">Vorschau nicht verfügbar</span>
      </div>
    {% endif %}
  </div>
  
  <div class="w-[480px] flex flex-col gap-6 overflow-y-auto pr-2">
    <div class="card p-8 bg-white">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-xl font-bold text-slate-900">Validierung</h1>
          <p class="text-xs font-bold muted uppercase tracking-widest">{{ filename }}</p>
        </div>
        <div class="badge bg-accent-50 text-accent-700 border-accent-100 font-bold">{{ confidence }}% Vertrauen</div>
      </div>
      {{ right|safe }}
    </div>
  </div>
</div>
"""

HTML_WIZARD = r"""
{% if is_duplicate %}
<div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700 font-bold shadow-sm mb-6 flex items-center gap-3">
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-amber-500"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>
  <div>Duplikat erkannt: Dokument bereits im Archiv.</div>
</div>
{% endif %}

{% if msg %}<div class="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-100 text-rose-700 text-xs font-bold shadow-sm">{{ msg }}</div>{% endif %}

<form method="post" class="space-y-6">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <input type="hidden" name="confirm" value="1">
  
  <div class="space-y-4">
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="space-y-1">
        <label class="muted text-[10px] font-bold uppercase tracking-widest px-1">Beleg-Typ</label>
        <select name="doctype" class="w-full rounded-xl border border-slate-200 p-3 text-sm font-bold bg-slate-50 focus:border-accent-500">
          {% for dt in doctypes %}
            <option value="{{dt}}" {{'selected' if w.doctype==dt or suggested_doctype==dt}}>{{dt}}</option>
          {% endfor %}
        </select>
      </div>
      <div class="space-y-1">
        <label class="muted text-[10px] font-bold uppercase tracking-widest px-1">Beleg-Datum</label>
        <input name="document_date" value="{{w.document_date or suggested_date}}" class="w-full rounded-xl border border-slate-200 p-3 text-sm bg-white focus:border-accent-500" placeholder="YYYY-MM-DD">
      </div>
    </div>

    <div class="space-y-1">
      <label class="muted text-[10px] font-bold uppercase tracking-widest px-1">Kundennummer (KDNR)</label>
      <input name="kdnr" value="{{w.kdnr}}" list="kdnr_list" class="w-full rounded-xl border border-slate-200 p-3 text-sm font-bold bg-white focus:border-accent-500" placeholder="z.B. 12345" required>
      <datalist id="kdnr_list">
        {% for k in kdnr_ranked %}<option value="{{k}}">{% endfor %}
      </datalist>
    </div>

    <div class="space-y-1">
      <label class="muted text-[10px] font-bold uppercase tracking-widest px-1">Name / Firma</label>
      <input name="name" value="{{w.name}}" class="w-full rounded-xl border border-slate-200 p-3 text-sm bg-white focus:border-accent-500">
    </div>
  </div>

  <div class="pt-6 border-t border-slate-50 flex gap-3">
    <button type="submit" class="flex-1 btn-primary py-4 shadow-lg">ARCHIVIEREN</button>
    <button type="submit" name="reextract" value="1" class="px-6 btn-outline bg-white shadow-sm font-bold text-xs" title="Neu analysieren">RESET</button>
  </div>
</form>
"""

# -------- Helper Functions ----------
def _render_base(content: str, active_tab: str = "upload"):
    return render_template_string(
        HTML_BASE,
        content=content,
        active_tab=active_tab,
        branding=Config.get_branding(),
        tenant=_norm_tenant(current_tenant() or "default"),
        roles=current_role(),
        user=current_user() or "-",
        profile=_get_profile(),
        ablage=str(BASE_PATH)
    )

def _get_profile() -> dict:
    if callable(getattr(core, "get_profile", None)):
        return core.get_profile()
    return {"name": "Standard Profil"}

def _norm_tenant(t: str) -> str:
    return (t or "default").upper()

def _safe_filename(fn: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", fn)

def _is_allowed_ext(fn: str) -> bool:
    return Path(fn).suffix.lower() in SUPPORTED_EXT

def _wizard_get(p: dict) -> dict:
    return p.get("wizard") or {}

def _card(level: str, text: str) -> str:
    c = {"error": "rose", "warn": "amber", "info": "blue"}.get(level, "slate")
    return f"<div class='card p-6 bg-{c}-50 border-{c}-200 text-{c}-700 text-sm font-medium'>{text}</div>"

def _resolve_doc_path(token: str, p: dict) -> Optional[Path]:
    path_str = p.get("path")
    if not path_str: return None
    path = Path(path_str)
    return path if path.exists() else None

# -------- Routes ----------

@bp.route("/")
@login_required
def index():
    user = current_user()
    items_meta = list_pending(username=user) or []
    
    # Optimization: Strip large fields for the index list
    items = []
    meta = {}
    for x in items_meta:
        t = x.get("_token")
        if t:
            items.append(t)
            # Remove large data from the meta dict used in the list view
            x.pop("preview", None)
            x.pop("extracted_text", None)
            meta[t] = x
            
    list_recent = _core_get("list_recent_docs")
    recent = list_recent(tenant_id=current_tenant()) if list_recent else []
    return _render_base(render_template_string(HTML_INDEX, items=items, meta=meta, recent=recent), active_tab="upload")

@bp.route("/upload", methods=["POST"])
@login_required
@csrf_protected
@upload_limiter.limit_required
def upload():
    current_app.logger.info(f"Upload request received from user {current_user()}")
    files = request.files.getlist("file")
    if not files:
        current_app.logger.warning("No files in upload request.")
        return jsonify(error="no_file"), 400
        
    tenant = _norm_tenant(current_tenant() or "default")
    results = []
    for f in files:
        if not f or not f.filename: continue
        fname = _safe_filename(f.filename)
        current_app.logger.info(f"Processing file: {fname} for tenant: {tenant}")
        
        if not _is_allowed_ext(fname):
            current_app.logger.warning(f"File extension not supported: {fname}")
            continue
            
        dest_dir = EINGANG / tenant
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}_{fname}"
        
        try:
            f.save(str(dest))
            current_app.logger.info(f"File saved to: {dest}")
            token = analyze_to_pending(dest, owner=current_user() or "")
            results.append({"token": token, "filename": fname})
            current_app.logger.info(f"Analysis triggered. Token: {token}")
        except Exception as e:
            current_app.logger.error(f"Error during upload processing for {fname}: {e}")
            pass
            
    if not results:
        return jsonify(error="unsupported", message="Keine gueltigen Dateien hochgeladen."), 400
        
    return jsonify(tokens=results)

@bp.route("/review/<token>/kdnr", methods=["GET", "POST"])
@login_required
@csrf_protected
def review(token: str):
    user, role = current_user() or "guest", current_role()
    p = read_pending(token)
    if not p: return _render_base(_card("error", "Beleg nicht gefunden."))
    
    # Locking
    now = datetime.now()
    locked_by, locked_at_str = p.get("locked_by", ""), p.get("locked_at", "")
    if locked_by and locked_by != user and role != "DEV":
        if locked_at_str:
            try:
                locked_at = datetime.fromisoformat(locked_at_str)
                if (now - locked_at).total_seconds() < 900:
                    return _render_base(_card("warn", f"Gesperrt durch {locked_by}"))
            except Exception: pass

    p["locked_by"], p["locked_at"] = user, now.isoformat()
    write_pending(token, p)

    if p.get("status") == "ANALYZING":
        return _render_base(render_template_string(HTML_REVIEW_SPLIT, token=token, filename=p.get("filename",""), is_pdf=True, right=_card("info","KI Analyse läuft..."), confidence=0))
    
    w = _wizard_get(p)
    msg = ""
    if request.method == "POST":
        if request.form.get("reextract") == "1":
            src = _resolve_doc_path(token, p)
            if src:
                delete_pending(token)
                new_t = analyze_to_pending(src, owner=current_user() or "", force_ocr=True)
                return redirect(url_for("web.review", token=new_t))
        if request.form.get("confirm") == "1":
            tenant = _norm_tenant(current_tenant() or w.get("tenant") or "default")
            answers = {
                "tenant": tenant, "kdnr": normalize_component(request.form.get("kdnr") or ""),
                "name": normalize_component(request.form.get("name") or "Kunde"),
                "doctype": (request.form.get("doctype") or "SONSTIGES").upper(),
                "document_date": normalize_component(request.form.get("document_date") or ""),
                "user": user,
            }
            if not answers["kdnr"]: msg = "KDNR fehlt."
            else:
                src = _resolve_doc_path(token, p)
                if src:
                    try:
                        process_with_answers(src, answers); delete_pending(token); return redirect(url_for("web.done_view", token=token))
                    except Exception as e: msg = f"Error: {e}"

    right = render_template_string(HTML_WIZARD, w=w, doctypes=DOCTYPE_CHOICES, suggested_doctype="SONSTIGES", suggested_date="", confidence=50, msg=msg)
    return _render_base(render_template_string(HTML_REVIEW_SPLIT, token=token, filename=p.get("filename",""), is_pdf=Path(p.get("filename","")).suffix.lower()==".pdf", preview=p.get("preview"), right=right, confidence=50), active_tab="upload")

@bp.route("/done/<token>")
@login_required
def done_view(token: str):
    html = f"<div class='card p-16 bg-white text-center max-w-xl mx-auto'><div class='h-24 w-24 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center mx-auto mb-8 shadow-xl border border-emerald-100'><svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3'><polyline points='20 6 9 17 4 12'/></svg></div><h1 class='text-3xl font-black mb-4'>Archiviert</h1><p class='muted mb-12 font-bold uppercase tracking-widest text-[10px]'>Dokument sicher im Ledger abgelegt</p><a class='btn-primary px-12 py-4' href='/'>Zur Übersicht</a></div>"
    return _render_base(html, active_tab="upload")

@bp.route("/mail")
@login_required
def mail(): return _render_base("<div class='card p-12 bg-white text-center'><h1 class='text-xl font-black'>Postfach</h1><p class='muted mt-4'>Keine neuen Nachrichten.</p></div>", active_tab="mail")

@bp.route("/tasks")
@login_required
def tasks(): return _render_base("<div class='card p-12 bg-white text-center'><h1 class='text-xl font-black'>Aufgaben</h1><p class='muted mt-4'>Alle Aufgaben erledigt.</p></div>", active_tab="tasks")

@bp.route("/time")
@login_required
def time_page(): return _render_base("<div class='card p-12 bg-white text-center'><h1 class='text-xl font-black'>Zeiterfassung</h1><p class='muted mt-4'>Zeiterfassung bereit.</p></div>", active_tab="time")

@bp.route("/assistant")
@login_required
def assistant_page(): return _render_base("<div class='card p-12 bg-white text-center'><h1 class='text-xl font-black'>Assistent</h1><p class='muted mt-4'>Wie kann ich Ihnen heute helfen?</p></div>", active_tab="assistant")

@bp.route("/chat")
@login_required
def chat(): return _render_base("<div class='card p-12 bg-white text-center'><h1 class='text-xl font-black'>Chat</h1><p class='muted mt-4'>Chat bereit.</p></div>", active_tab="chat")

@bp.route("/settings")
@login_required
def settings_page(): return _render_base("<div class='card p-12 bg-white text-center'><h1 class='text-xl font-black'>Konfiguration</h1><p class='muted mt-4'>Systemeinstellungen sind optimiert.</p></div>", active_tab="settings")

@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        u, p = request.form.get("username"), request.form.get("password")
        auth_db: AuthDB = current_app.extensions["auth_db"]
        user_row = auth_db.get_user(u)
        if user_row and user_row.password_hash == hash_password(p):
            m = auth_db.get_memberships(u)
            if m: login_user(u, m[0].role, m[0].tenant_id); return redirect(url_for("web.index"))
            error = "Keine Mandanten-Zuordnung."
        else: error = "Identität konnte nicht verifiziert werden."
    return render_template_string(HTML_LOGIN, error=error, branding=Config.get_branding())

@bp.route("/logout")
def logout(): logout_user(); return redirect(url_for("web.login"))

@bp.route("/health")
def health():
    from .lifecycle import manager
    return jsonify(ok=True, state=manager.state.value, details=manager.details, uptime=manager.uptime)

@bp.route("/api/progress/<token>")
@login_required
def api_progress(token: str):
    p = read_pending(token)
    if not p: return jsonify(status="ERROR"), 404
    return jsonify(status=p.get("status", "ANALYZING"), progress=p.get("progress", 0), progress_phase=p.get("progress_phase", ""))

@bp.route("/file/<token>")
@login_required
def file_preview(token: str):
    p = read_pending(token)
    if not p or not p.get("path"): abort(404)
    return send_file(p["path"])
