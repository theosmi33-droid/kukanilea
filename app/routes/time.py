from __future__ import annotations
import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app, render_template_string
from app.auth import login_required, current_tenant, current_user, current_role, require_role
from app.security import csrf_protected
from app.errors import json_error
from app.contracts.tool_contracts import build_tool_health, build_tool_summary

# Core extractors
from app.core import (
    time_project_list,
    time_project_create,
    time_entry_start,
    time_entry_stop,
    time_entry_list,
    time_entry_update,
    time_entry_approve,
    time_entries_export_csv
)

logger = logging.getLogger("kukanilea.time")
bp = Blueprint("time", __name__)

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

@bp.route("/time")
@login_required
def time_tracking():
    from app.web import _render_base
    if not callable(time_entry_list):
        html = """<div class='rounded-2xl bg-slate-900/60 border border-slate-800 p-5 card'>
          <div class='text-lg font-semibold'>Time Tracking</div>
          <div class='muted text-sm mt-2'>Time Tracking ist im Core nicht verfügbar.</div>
        </div>"""
        return _render_base(html, active_tab="time")
    return _render_base(
        render_template_string(HTML_TIME, role=current_role()), active_tab="time"
    )

@bp.get("/api/time/projects")
@login_required
def api_time_projects():
    if not callable(time_project_list):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    projects = time_project_list(tenant_id=current_tenant(), status="ACTIVE")
    return jsonify(ok=True, projects=projects)

@bp.post("/api/time/projects")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_projects_create():
    if not callable(time_project_create):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    try:
        project = time_project_create(
            tenant_id=current_tenant(),
            name=name,
            description=description,
            created_by=current_user() or "",
        )
    except ValueError as exc:
        return json_error(str(exc), "Projekt konnte nicht angelegt werden.", status=400)
    # RAG enqueue simplified for now
    return jsonify(ok=True, project=project)

@bp.post("/api/time/start")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_start():
    if not callable(time_entry_start):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    note = (payload.get("note") or "").strip()
    try:
        entry = time_entry_start(
            tenant_id=current_tenant(),
            user=current_user() or "",
            project_id=int(project_id) if project_id else None,
            note=note,
        )
    except ValueError as exc:
        return json_error(str(exc), "Timer konnte nicht gestartet werden.", status=400)
    return jsonify(ok=True, entry=entry)

@bp.post("/api/time/stop")
@login_required
@csrf_protected
@require_role("OPERATOR")
def api_time_stop():
    if not callable(time_entry_stop):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    try:
        entry = time_entry_stop(
            tenant_id=current_tenant(),
            user=current_user() or "",
            entry_id=int(entry_id) if entry_id else None,
        )
    except ValueError as exc:
        return json_error(str(exc), "Timer konnte nicht gestoppt werden.", status=400)
    return jsonify(ok=True, entry=entry)

@bp.get("/api/time/entries")
@login_required
def api_time_entries():
    if not callable(time_entry_list):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    range_name = (request.args.get("range") or "week").strip().lower()
    date_value = (request.args.get("date") or datetime.now().date().isoformat()).strip()
    user = (request.args.get("user") or "").strip()
    if current_role() not in {"ADMIN", "DEV"}:
        user = current_user() or ""
    start_at, end_at = _time_range_params(range_name, date_value)
    entries = time_entry_list(
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
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    if not entry_id:
        return json_error("entry_id_required", "Eintrag fehlt.", status=400)
    try:
        entry = time_entry_update(
            tenant_id=current_tenant(),
            entry_id=int(entry_id),
            project_id=(int(payload.get("project_id")) if payload.get("project_id") else None),
            start_at=(payload.get("start_at") or None),
            end_at=(payload.get("end_at") or None),
            note=payload.get("note"),
            user=current_user() or "",
        )
    except ValueError as exc:
        return json_error(str(exc), "Eintrag konnte nicht aktualisiert werden.", status=400)
    return jsonify(ok=True, entry=entry)

@bp.post("/api/time/entry/approve")
@login_required
@csrf_protected
@require_role("ADMIN")
def api_time_entry_approve():
    if not callable(time_entry_approve):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    payload = request.get_json(silent=True) or {}
    entry_id = payload.get("entry_id")
    if not entry_id:
        return json_error("entry_id_required", "Eintrag fehlt.", status=400)
    try:
        entry = time_entry_approve(
            tenant_id=current_tenant(),
            entry_id=int(entry_id),
            approved_by=current_user() or "",
        )
    except ValueError as exc:
        return json_error(str(exc), "Eintrag konnte nicht freigegeben werden.", status=400)
    return jsonify(ok=True, entry=entry)

@bp.get("/api/time/export")
@login_required
def api_time_export():
    if not callable(time_entries_export_csv):
        return json_error("feature_unavailable", "Time Tracking ist nicht verfügbar.", status=501)
    range_name = (request.args.get("range") or "week").strip().lower()
    date_value = (request.args.get("date") or datetime.now().date().isoformat()).strip()
    user = (request.args.get("user") or "").strip()
    if current_role() not in {"ADMIN", "DEV"}:
        user = current_user() or ""
    start_at, end_at = _time_range_params(range_name, date_value)
    csv_payload = time_entries_export_csv(
        tenant_id=current_tenant(),
        user=user or None,
        start_at=start_at,
        end_at=end_at,
    )
    response = current_app.response_class(csv_payload, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=time_entries.csv"
    return response

@bp.get("/api/time/summary")
@login_required
def api_time_summary():
    tenant = str(current_tenant() or "default")
    return jsonify(build_tool_summary("time", tenant=tenant))

@bp.get("/api/time/health")
@login_required
def api_time_health():
    tenant = str(current_tenant() or "default")
    payload = build_tool_health("time", tenant=tenant)
    code = 200 if payload.get("status") in {"ok", "degraded"} else 503
    return jsonify(payload), code
