#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from pathlib import Path

from flask import Flask, request, jsonify, render_template_string, send_file, abort, redirect, url_for

from tophandwerk_core import (
    EINGANG, BASE_PATH, PENDING_DIR, DONE_DIR, SUPPORTED_EXT,
    # stabiler Contract: analyze_to_pending ist Alias auf start_background_analysis
    analyze_to_pending, read_pending, write_pending, delete_pending, list_pending,
    write_done, read_done,
    process_with_answers, normalize_component,
    find_existing_customer_folders, parse_folder_fields, best_match_object_folder
)

APP = Flask(__name__)
PORT = int(os.environ.get("PORT", 5051))


# =========================
# UI (Tailwind CDN) + Theme/Accent Persist
# =========================
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

  /* light */
  .light body { background:#f8fafc !important; color:#0f172a !important; }
  .light .card { background:rgba(255,255,255,.95) !important; border-color:#e2e8f0 !important; }
  .light .muted { color:#475569 !important; }
  .light .input { background:#ffffff !important; border-color:#cbd5e1 !important; color:#0f172a !important; }
  .light .btn-outline{ border-color:#cbd5e1 !important; }
  .light .pickbtn{ background:#ffffff !important; color:#0f172a !important; border-color:#cbd5e1 !important; }

  .accentText{ color:var(--accent-500); }
</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
<div class="max-w-7xl mx-auto p-6">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-3xl font-bold">Tophandwerk</h1>
      <div class="muted text-sm">Upload → Analyse → Review → Ablage</div>
      <div class="muted text-xs mt-1">Eingang: {{eingang}} • Ablage: {{ablage}}</div>
    </div>
    <div class="flex items-center gap-2">
      <button id="accentBtn" class="rounded-xl px-3 py-2 text-sm card btn-outline">
        Accent: <span id="accentLabel"></span>
      </button>
      <button id="themeBtn" class="rounded-xl px-3 py-2 text-sm card btn-outline">
        Theme: <span id="themeLabel"></span>
      </button>
    </div>
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

HTML_INDEX = r"""
<div class="grid md:grid-cols-2 gap-6">
  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Datei hochladen</div>
    <div class="muted text-sm mb-4">
      Unterstützt: PDF, JPG, PNG, TIFF. Nach Upload startet Background-Analyse; Review öffnet automatisch.
    </div>

    <form id="upform" class="space-y-3">
      <input id="file" name="file" type="file"
        class="block w-full text-sm input
        file:mr-4 file:rounded-xl file:border-0 file:bg-slate-700 file:px-4 file:py-2
        file:text-sm file:font-semibold file:text-white hover:file:bg-slate-600" />
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
  </div>

  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    <div class="text-lg font-semibold mb-2">Review Queue</div>
    <div class="muted text-sm mb-4">
      Dateien bleiben hier, bis sie bestätigt sind.
    </div>

    {% if items %}
      <div class="space-y-2">
        {% for it in items %}
          <a class="block rounded-xl border border-slate-800 hover:border-slate-600 px-3 py-2"
             href="/review/{{it}}/kdnr">
            <div class="text-sm font-semibold">Review</div>
            <div class="muted text-xs">{{it}}</div>
          </a>
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

function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

async function pollProgress(token){
  // Polling: bis READY oder ERROR
  for(let i=0;i<2400;i++){ // max ~20min (0.5s * 2400)
    const res = await fetch("/api/progress/" + token, {cache:"no-store"});
    if(!res.ok){ await sleep(500); continue; }
    const j = await res.json();
    const pct = (typeof j.progress === "number") ? j.progress : 0;
    const ph = j.progress_phase || "";
    setProgress(pct);
    phase.textContent = ph;
    if(j.status === "READY"){
      status.textContent = "Analyse fertig. Review öffnet…";
      await sleep(150);
      window.location.href = "/review/" + token + "/kdnr";
      return;
    }
    if(j.status === "ERROR"){
      status.textContent = "Analyse-Fehler: " + (j.error || "unbekannt");
      return;
    }
    await sleep(500);
  }
  status.textContent = "Analyse dauert ungewöhnlich lange. Bitte Seite neu laden oder Queue prüfen.";
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = fileInput.files[0];
  if(!f){ status.textContent = "Bitte eine Datei auswählen."; return; }

  const ext = (f.name.split(".").pop() || "").toLowerCase();
  const ok = ["pdf","jpg","jpeg","png","tif","tiff","bmp"].includes(ext);
  if(!ok){
    status.textContent = "Nicht unterstützt. Bitte PDF/JPG/PNG/TIFF/BMP hochladen.";
    return;
  }

  const fd = new FormData();
  fd.append("file", f);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/upload", true);

  // Upload progress nur für Upload, nicht für Analyse
  xhr.upload.onprogress = (ev) => {
    if(ev.lengthComputable){
      setProgress((ev.loaded / ev.total) * 30); // Upload = 0..30%
    }
  };

  xhr.onload = () => {
    if(xhr.status === 200){
      const resp = JSON.parse(xhr.responseText);
      status.textContent = "Upload OK. Analyse startet…";
      phase.textContent = "Start";
      // Analyse-Progress belegt 30..100% (wir mappen im Poll einfach 0..100 aus Core; UI zeigt direkt)
      pollProgress(resp.token);
    } else {
      status.textContent = "Fehler beim Upload: HTTP " + xhr.status;
    }
  };

  xhr.onerror = () => { status.textContent = "Upload fehlgeschlagen (Netzwerk/Server)."; };
  status.textContent = "Upload läuft…";
  phase.textContent = "";
  setProgress(0);
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
        <iframe src="/file/{{token}}" class="w-full" style="height:980px"></iframe>
      {% else %}
        <img src="/file/{{token}}" class="w-full"/>
      {% endif %}
    </div>

    {% if preview %}
      <div class="mt-4">
        <div class="text-sm font-semibold mb-2">Top-Zeilen (Bold/Font/Mitte gewichtet)</div>
        <pre class="text-xs whitespace-pre-wrap rounded-xl border border-slate-800 p-3 bg-slate-950/40 max-h-64 overflow-auto">{{preview}}</pre>
      </div>
    {% endif %}
  </div>

  <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card">
    {{ right|safe }}
  </div>
</div>
"""

HTML_NOT_FOUND = r"""
<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card max-w-xl">
  <div class="text-xl font-semibold mb-2">Review nicht gefunden</div>
  <div class="muted text-sm mb-4">
    Der Review-Token existiert nicht mehr (z.B. bereits abgelegt oder Pending-Datei gelöscht).
  </div>
  <a class="rounded-xl px-4 py-2 font-semibold btn-primary inline-block" href="/">Zur Übersicht</a>
</div>
"""

HTML_DONE = r"""
<div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card">
  <div class="text-2xl font-bold mb-2">Fertig</div>
  <div class="muted text-sm mb-4">Zusammenfassung der Ablage</div>

  <div class="grid md:grid-cols-2 gap-4">
    <div class="rounded-xl border border-slate-800 p-4">
      <div class="text-sm font-semibold mb-2">Bestätigte Daten</div>
      <div class="text-sm">Kundennummer: <span class="font-semibold">{{kdnr}}</span></div>
      <div class="text-sm">Name/Firma: <span class="font-semibold">{{name}}</span></div>
      <div class="text-sm">Adresse: <span class="font-semibold">{{addr}}</span></div>
      <div class="text-sm">PLZ/Ort: <span class="font-semibold">{{plzort}}</span></div>
      <div class="text-sm mt-2">Objekt: <span class="font-semibold">{{objmode}}</span></div>
      <div class="text-sm">Dokumenttyp: <span class="font-semibold">{{doctype}}</span></div>
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

      <div class="muted text-xs mt-3">Status</div>
      <div class="text-sm">
        {% if created_new %}
          Neues Objekt angelegt
        {% else %}
          Bestehendes Objekt genutzt
        {% endif %}
      </div>
    </div>
  </div>

  <div class="mt-5 flex gap-2">
    <a class="rounded-xl px-4 py-2 font-semibold btn-primary" href="/">Zur Übersicht</a>
  </div>
</div>
"""

def _card_error(msg: str) -> str:
    return f"""
      <div class="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm">
        {msg}
      </div>
    """

def _card_info(msg: str) -> str:
    return f"""
      <div class="rounded-xl border border-slate-700 bg-slate-950/40 p-3 text-sm">
        {msg}
      </div>
    """

def _render_base(content: str):
    return render_template_string(
        HTML_BASE,
        content=content,
        eingang=str(EINGANG),
        ablage=str(BASE_PATH),
    )

def _render_review(token: str, right_html: str):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    filename = p.get("filename", "")
    used_ocr = bool(p.get("used_ocr", False))
    preview = p.get("preview", "")
    is_pdf = (Path(filename).suffix.lower() == ".pdf")

    return _render_base(
        render_template_string(
            HTML_REVIEW_SHELL,
            token=token,
            filename=filename,
            used_ocr=used_ocr,
            preview=preview,
            is_pdf=is_pdf,
            right=right_html
        )
    )

def _wizard_get(p: dict) -> dict:
    w = p.get("wizard") or {}
    w.setdefault("kdnr", "")
    w.setdefault("use_existing", "")
    w.setdefault("name", "")
    w.setdefault("addr", "")
    w.setdefault("plzort", "")
    w.setdefault("doctype", "")  # user choice
    w.setdefault("customer_status", "")  # "BESTAND" / "NEU"
    return w

def _wizard_save(token: str, p: dict, w: dict):
    p["wizard"] = w
    write_pending(token, p)


# =========================
# ROUTES
# =========================
@APP.route("/")
def index():
    items = [x["_token"] for x in list_pending()]
    return _render_base(render_template_string(HTML_INDEX, items=items))

@APP.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="no file"), 400

    filename = f.filename.replace("\\", "_").replace("/", "_").strip()
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXT:
        return jsonify(error="unsupported"), 400

    EINGANG.mkdir(parents=True, exist_ok=True)
    dest = EINGANG / filename
    if dest.exists():
        dest = EINGANG / f"{int(time.time())}_{filename}"

    f.save(dest)

    token = analyze_to_pending(dest)
    return jsonify(token=token, review_url=f"/review/{token}/kdnr")

@APP.route("/api/progress/<token>")
def api_progress(token):
    p = read_pending(token)
    if not p:
        return jsonify(error="not_found"), 404
    return jsonify(
        status=p.get("status", ""),
        progress=float(p.get("progress", 0.0) or 0.0),
        progress_phase=p.get("progress_phase", ""),
        error=p.get("error", ""),
    )

@APP.route("/file/<token>")
def file_preview(token):
    p = read_pending(token)
    if not p:
        abort(404)
    file_path = Path(p.get("path", ""))
    if not file_path.exists():
        abort(404)
    return send_file(file_path, as_attachment=False)

@APP.route("/review/<token>", methods=["GET", "POST"])
def review_compat(token):
    step = request.args.get("step", "").strip()
    if step == "2":
        return redirect(url_for("review_name", token=token))
    if step == "3":
        return redirect(url_for("review_addr", token=token))
    if step == "4":
        return redirect(url_for("review_plz", token=token))
    if step == "5":
        return redirect(url_for("review_doctype", token=token))
    return redirect(url_for("review_kdnr", token=token))

@APP.route("/done/<token>")
def done_view(token):
    d = read_done(token)
    if not d:
        return _render_base(HTML_NOT_FOUND)

    html = render_template_string(
        HTML_DONE,
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
    )
    return _render_base(html)


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
    show_extracted: bool = True
):
    sug_buttons = ""

    if show_scores and ranked:
        for num, score in ranked[:6]:
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
        for s in suggestions[:6]:
            s_esc = str(s).replace('"', "&quot;")
            sug_buttons += f"""
              <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl"
                data-fill="{s_esc}">
                {s}
              </button>
            """

    err_html = _card_error(error) if error else ""

    extracted_panel = ""
    if show_extracted:
        p = read_pending(token) or {}
        extracted = (p.get("extracted_text") or "")
        if extracted:
            extracted_panel = f"""
              <div class="mt-6">
                <div class="text-sm font-semibold mb-2">Extrahierter Text (copy/paste)</div>
                <textarea class="w-full text-xs rounded-xl border border-slate-800 p-3 bg-slate-950/40 input"
                  style="height:260px" readonly>{extracted}</textarea>
                <div class="muted text-xs mt-1">Tipp: Markieren und kopieren. OCR/Textlayer kann Fehler enthalten.</div>
              </div>
            """

    right = f"""
      <form method="post" class="space-y-4" autocomplete="off">
        <div>
          <div class="text-lg font-semibold mb-1">{title}</div>
          <div class="muted text-sm">{subtitle}</div>
        </div>

        <div>
          <label class="muted text-xs">Eingabe (direkt tippen)</label>
          <input id="mainInput" class="w-full rounded-xl bg-slate-800 border border-slate-700 p-2 input"
            name="{field_name}" placeholder="{title}" value="{current_value or ''}">
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
          <button class="rounded-xl px-4 py-2 font-semibold btn-primary" name="next" value="1">Weiter</button>
          <a class="rounded-xl px-4 py-2 font-semibold btn-outline card" href="/">Abbrechen</a>
        </div>
      </form>

      {extracted_panel}

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


@APP.route("/review/<token>/kdnr", methods=["GET", "POST"])
def review_kdnr(token):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    # Noch nicht fertig? dann Warteseite mit Auto-Refresh
    if p.get("status") not in ("READY", "ERROR"):
        wait = f"""
        <div class="rounded-2xl bg-slate-900/60 border border-slate-800 p-6 card max-w-xl">
          <div class="text-xl font-semibold mb-2">Analyse läuft…</div>
          <div class="muted text-sm mb-4">{p.get("progress_phase","")}</div>
          <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
            <div id="bar" class="h-3" style="width:{float(p.get("progress",0.0) or 0.0)}%; background:var(--accent-500)"></div>
          </div>
          <div class="muted text-xs mt-2" id="pct">{float(p.get("progress",0.0) or 0.0):.1f}%</div>
          <script>
            async function tick(){{
              const res = await fetch("/api/progress/{token}", {{cache:"no-store"}});
              if(!res.ok) return;
              const j = await res.json();
              const b = document.getElementById("bar");
              const pct = document.getElementById("pct");
              const p = Math.max(0, Math.min(100, (j.progress||0)));
              b.style.width = p + "%";
              pct.textContent = p.toFixed(1) + "% • " + (j.progress_phase||"");
              if(j.status === "READY") window.location.href = "/review/{token}/kdnr";
              if(j.status === "ERROR") pct.textContent = "Fehler: " + (j.error||"unbekannt");
            }}
            setInterval(tick, 500);
          </script>
          <div class="mt-4"><a class="underline text-sm" href="/">Zur Übersicht</a></div>
        </div>
        """
        return _render_base(wait)

    if p.get("status") == "ERROR":
        return _render_base(_card_error("Analyse fehlgeschlagen: " + (p.get("error") or "unbekannt")) + '<div class="mt-3"><a class="underline text-sm" href="/">Zur Übersicht</a></div>')

    w = _wizard_get(p)
    ranked = (p.get("kdnr_ranked") or [])
    suggestions = [x[0] for x in ranked[:6]] if ranked else []

    if request.method == "POST":
        val = normalize_component(request.form.get("kdnr", "") or "")
        use_existing = (request.form.get("use_existing") or "").strip()
        adopt_existing = (request.form.get("adopt_existing") or "").strip() == "1"

        if not val:
            return _step_form(
                token=token,
                title="1) Kundennummer",
                subtitle="Direkt tippen oder Vorschlag anklicken. Weiter bestätigt.",
                field_name="kdnr",
                current_value=w.get("kdnr", ""),
                suggestions=suggestions,
                ranked=ranked,
                show_scores=True,
                error="Bitte Kundennummer eingeben oder Vorschlag anklicken."
            )

        w["kdnr"] = val
        w["use_existing"] = use_existing.strip()

        existing = find_existing_customer_folders(BASE_PATH, val)
        w["customer_status"] = "BESTAND" if existing else "NEU"

        objs = []
        for f in existing:
            fields = parse_folder_fields(f.name)
            objs.append({
                "folder": f.name,
                "path": str(f),
                "name": fields.get("name", ""),
                "addr": fields.get("addr", ""),
                "plzort": fields.get("plzort", ""),
            })
        p["existing_objects"] = objs

        if existing:
            best_path, best_score = best_match_object_folder(existing, w.get("addr", ""), w.get("plzort", ""))
            if (best_path is None) and existing:
                best_path = existing[0]
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
                if adopt_existing or (request.form.get("adopt_existing") is None):
                    if not w.get("name") and bf.get("name"):
                        w["name"] = bf.get("name")
                    if not w.get("addr") and bf.get("addr"):
                        w["addr"] = bf.get("addr")
                    if not w.get("plzort") and bf.get("plzort"):
                        w["plzort"] = bf.get("plzort")
                    if not w.get("use_existing"):
                        w["use_existing"] = str(best_path)

        _wizard_save(token, p, w)
        return redirect(url_for("review_name", token=token))

    extra = ""
    if w.get("kdnr"):
        existing = p.get("existing_objects") or []
        if existing:
            best = p.get("best_existing") or {}
            best_line = ""
            if best:
                best_line = f"""
                  <div class="muted text-xs mt-2">Vorschlag aus Bestand:</div>
                  <div class="text-sm"><span class="font-semibold">{best.get("folder","")}</span></div>
                  <div class="muted text-xs">{best.get("addr","")} • {best.get("plzort","")}</div>
                """

            items = """
              <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl" data-obj="__new__">
                Neues Objekt anlegen
              </button>
            """
            for o in existing[:10]:
                folder = o.get("folder", "")
                addr = o.get("addr", "")
                plzort = o.get("plzort", "")
                path_esc = (o.get("path","") or "").replace('"', "&quot;")
                items += f"""
                  <button type="button" class="pickbtn text-left px-3 py-2 rounded-xl" data-objpath="{path_esc}">
                    <div class="text-sm font-semibold">{folder}</div>
                    <div class="muted text-xs">{addr} • {plzort}</div>
                  </button>
                """

            chosen = "Neues Objekt"
            if w.get("use_existing"):
                try:
                    chosen = Path(w.get("use_existing")).name
                except Exception:
                    chosen = "Bestehendes Objekt"

            extra = f"""
              {_card_info("Bestandskunde erkannt (nur über Kundennummer). Bitte prüfen, ob Name/Adresse stimmen.")}
              <div class="rounded-xl border border-slate-800 p-3 mt-3">
                <div class="text-sm font-semibold mb-2">Bestands-Objekt (optional)</div>
                <div class="muted text-xs mb-3">Objekt wählen (verhindert doppelte Ordner) oder „Neues Objekt“.</div>

                <input type="hidden" id="objInput" name="use_existing" value="{(w.get('use_existing') or '').replace('"', '&quot;')}">

                <label class="flex items-center gap-2 text-sm mb-3">
                  <input type="checkbox" name="adopt_existing" value="1" checked>
                  <span>Bestandsdaten (Name/Adresse/PLZ) als Vorschlag übernehmen</span>
                </label>

                <div class="grid gap-2">{items}</div>
                <div class="muted text-xs mt-2">Aktuell gewählt: <span class="font-semibold">{chosen}</span></div>
                {best_line}
              </div>

              <script>
              (function(){{
                const objInput = document.getElementById("objInput");
                document.querySelectorAll("[data-objpath]").forEach(btn => {{
                  btn.addEventListener("click", () => {{
                    const v = btn.getAttribute("data-objpath");
                    objInput.value = v || "";
                  }});
                }});
              }})();
              </script>
            """
        else:
            extra = _card_info("Kundennummer nicht gefunden: Neuer Kunde. Empfehlung: falls unsicher, neue Kundennummer vergeben, um Vermischung zu vermeiden.")

    prefill = w.get("kdnr") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="1) Kundennummer",
        subtitle="Direkt tippen oder Vorschlag anklicken. Weiter bestätigt.",
        field_name="kdnr",
        current_value=prefill,
        suggestions=suggestions,
        ranked=ranked,
        show_scores=True,
        extra_html=extra
    )


@APP.route("/review/<token>/name", methods=["GET", "POST"])
def review_name(token):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggestions = (p.get("name_suggestions") or ["Kunde"])[:6]
    if w.get("name"):
        suggestions = [w.get("name")] + [s for s in suggestions if s != w.get("name")]

    if request.method == "POST":
        val = normalize_component(request.form.get("name", "") or "")
        if not val:
            return _step_form(
                token=token,
                title="2) Name / Firma",
                subtitle="Wenn es aus dem Bestand stimmt: einfach Weiter (Feld ist vorgefüllt).",
                field_name="name",
                current_value=w.get("name", ""),
                suggestions=suggestions,
                error="Bitte Name/Firma eingeben oder Vorschlag anklicken."
            )
        w["name"] = val
        _wizard_save(token, p, w)
        return redirect(url_for("review_addr", token=token))

    prefill = w.get("name") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="2) Name / Firma",
        subtitle="Wenn es aus dem Bestand stimmt: einfach Weiter (Feld ist vorgefüllt).",
        field_name="name",
        current_value=prefill,
        suggestions=suggestions
    )


@APP.route("/review/<token>/addr", methods=["GET", "POST"])
def review_addr(token):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggestions = (p.get("addr_suggestions") or ["Adresse"])[:6]
    if w.get("addr"):
        suggestions = [w.get("addr")] + [s for s in suggestions if s != w.get("addr")]

    if request.method == "POST":
        val = normalize_component(request.form.get("addr", "") or "")
        if not val:
            return _step_form(
                token=token,
                title="3) Adresse (Straße + Nr)",
                subtitle="Wenn es aus dem Bestand stimmt: einfach Weiter (Feld ist vorgefüllt).",
                field_name="addr",
                current_value=w.get("addr", ""),
                suggestions=suggestions,
                error="Bitte Adresse eingeben oder Vorschlag anklicken."
            )
        w["addr"] = val
        _wizard_save(token, p, w)
        return redirect(url_for("review_plz", token=token))

    prefill = w.get("addr") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="3) Adresse (Straße + Nr)",
        subtitle="Wenn es aus dem Bestand stimmt: einfach Weiter (Feld ist vorgefüllt).",
        field_name="addr",
        current_value=prefill,
        suggestions=suggestions
    )


@APP.route("/review/<token>/plz", methods=["GET", "POST"])
def review_plz(token):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))

    suggestions = (p.get("plzort_suggestions") or ["PLZ Ort"])[:6]
    if w.get("plzort"):
        suggestions = [w.get("plzort")] + [s for s in suggestions if s != w.get("plzort")]

    def summary_box():
        obj_txt = "Neues Objekt"
        if w.get("use_existing"):
            try:
                obj_txt = Path(w.get("use_existing")).name
            except Exception:
                obj_txt = "Bestehendes Objekt"
        dt = w.get("doctype") or (p.get("doctype_suggested") or "SONSTIGES")
        return f"""
          <div class="rounded-xl border border-slate-800 p-3">
            <div class="muted text-xs mb-2">Zusammenfassung</div>
            <div class="text-sm">Kundennr: <span class="font-semibold">{w.get('kdnr') or '-'}</span></div>
            <div class="text-sm">Kundenstatus: <span class="font-semibold">{w.get('customer_status') or '-'}</span></div>
            <div class="text-sm">Objekt: <span class="font-semibold">{obj_txt}</span></div>
            <div class="text-sm">Name: <span class="font-semibold">{w.get('name') or '-'}</span></div>
            <div class="text-sm">Adresse: <span class="font-semibold">{w.get('addr') or '-'}</span></div>
            <div class="text-sm">PLZ/Ort: <span class="font-semibold">{w.get('plzort') or '-'}</span></div>
            <div class="text-sm">Dokumenttyp: <span class="font-semibold">{dt}</span></div>
          </div>
        """

    if request.method == "POST":
        val = normalize_component(request.form.get("plzort", "") or "")
        if not val:
            return _step_form(
                token=token,
                title="4) PLZ + Ort",
                subtitle="Direkt tippen oder Vorschlag anklicken.",
                field_name="plzort",
                current_value=w.get("plzort", ""),
                suggestions=suggestions,
                extra_html=summary_box(),
                error="Bitte PLZ/Ort eingeben oder Vorschlag anklicken."
            )

        w["plzort"] = val
        _wizard_save(token, p, w)
        return redirect(url_for("review_doctype", token=token))

    prefill = w.get("plzort") or (suggestions[0] if suggestions else "")
    return _step_form(
        token=token,
        title="4) PLZ + Ort",
        subtitle="Direkt tippen oder Vorschlag anklicken.",
        field_name="plzort",
        current_value=prefill,
        suggestions=suggestions,
        extra_html=summary_box()
    )


@APP.route("/review/<token>/doctype", methods=["GET", "POST"])
def review_doctype(token):
    p = read_pending(token)
    if not p:
        return _render_base(HTML_NOT_FOUND)

    w = _wizard_get(p)
    if not w.get("kdnr"):
        return redirect(url_for("review_kdnr", token=token))
    if not w.get("plzort"):
        return redirect(url_for("review_plz", token=token))

    suggested = (p.get("doctype_suggested") or "SONSTIGES").upper()
    doctype_list = ["ANGEBOT","RECHNUNG","AUFTRAGSBESTAETIGUNG","AW","MAHNUNG","NACHTRAG","SONSTIGES"]

    if request.method == "POST":
        dt = (request.form.get("doctype") or "").upper().strip()
        if dt not in doctype_list:
            dt = "SONSTIGES"
        w["doctype"] = dt
        _wizard_save(token, p, w)

        src = Path(p.get("path", ""))
        if not src.exists():
            return _render_base(_card_error("Datei im Eingang nicht gefunden (evtl. verschoben/gelöscht).") + '<a class="underline text-sm" href="/">Zur Übersicht</a>')

        answers = {
            "kdnr": w.get("kdnr", ""),
            "use_existing": w.get("use_existing", ""),
            "name": w.get("name", "Kunde"),
            "addr": w.get("addr", "Adresse"),
            "plzort": w.get("plzort", "PLZ Ort"),
            "doctype": w.get("doctype", "SONSTIGES"),
        }

        try:
            folder, final_path, created_new = process_with_answers(src, answers)
        except Exception as e:
            return _render_base(_card_error(f"Ablage fehlgeschlagen: {e}") + '<a class="underline text-sm" href="/">Zur Übersicht</a>')

        done_payload = {
            "kdnr": answers["kdnr"],
            "name": answers["name"],
            "addr": answers["addr"],
            "plzort": answers["plzort"],
            "doctype": answers.get("doctype", "SONSTIGES"),
            "folder": str(folder),
            "final_path": str(final_path),
            "created_new": bool(created_new),
            "objmode": ("Bestehendes Objekt" if answers.get("use_existing") else "Neues Objekt"),
            "customer_status": (w.get("customer_status") or ("BESTAND" if answers.get("use_existing") else "NEU")),
        }
        write_done(token, done_payload)
        delete_pending(token)

        return redirect(url_for("done_view", token=token))

    # GET
    buttons = ""
    for dt in doctype_list:
        active = "border-[var(--accent-500)]" if (w.get("doctype") or suggested) == dt else "border-slate-800"
        hint = " (Vorschlag)" if dt == suggested else ""
        buttons += f"""
          <button type="submit" name="doctype" value="{dt}"
            class="pickbtn text-left px-3 py-2 rounded-xl {active}">
            <div class="font-semibold">{dt}{hint}</div>
          </button>
        """

    right = f"""
      <form method="post" class="space-y-4">
        <div>
          <div class="text-lg font-semibold mb-1">5) Dokumenttyp</div>
          <div class="muted text-sm">KI schlägt vor, du entscheidest. Klick = Auswahl + Ablage.</div>
        </div>

        <div class="rounded-xl border border-slate-800 p-3">
          <div class="muted text-xs">Vorschlag aus Analyse</div>
          <div class="text-sm font-semibold">{suggested}</div>
        </div>

        <div class="grid gap-2">
          {buttons}
        </div>

        <div class="pt-2">
          <a class="rounded-xl px-4 py-2 font-semibold btn-outline card inline-block" href="/review/{token}/plz">Zurück</a>
        </div>
      </form>

      <div class="mt-6">
        <div class="text-sm font-semibold mb-2">Extrahierter Text (copy/paste)</div>
        <textarea class="w-full text-xs rounded-xl border border-slate-800 p-3 bg-slate-950/40 input"
          style="height:260px" readonly>{(p.get("extracted_text") or "")}</textarea>
        <div class="muted text-xs mt-1">Tipp: Markieren und kopieren. OCR/Textlayer kann Fehler enthalten.</div>
      </div>
    """
    return _render_review(token, right)


# =========================
# START
# =========================
if __name__ == "__main__":
    EINGANG.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BASE_PATH.mkdir(parents=True, exist_ok=True)

    print(f"http://127.0.0.1:{PORT}")
    # use_reloader=False verhindert Doppelstart (Port belegt / Threads doppelt)
    APP.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
