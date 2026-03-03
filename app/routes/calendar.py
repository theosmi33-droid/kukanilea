from __future__ import annotations

from flask import Blueprint, render_template, session
from app.auth import login_required, current_tenant
from app.knowledge.ics_source import knowledge_calendar_events_list

bp = Blueprint("calendar", __name__)

@bp.route("/calendar")
@login_required
def show_calendar():
    tenant_id = current_tenant() or session.get("tenant_id") or "default"
    events = knowledge_calendar_events_list(tenant_id)
    return render_template("calendar.html", events=events)
