from __future__ import annotations

from pathlib import Path

from flask import Blueprint, render_template, session, Response, current_app
from app.auth import login_required, current_tenant
from app.knowledge.ics_source import knowledge_calendar_events_list, knowledge_ics_build_local_feed

bp = Blueprint("calendar", __name__)

@bp.route("/calendar")
@login_required
def show_calendar():
    tenant_id = current_tenant() or session.get("tenant_id") or "default"
    try:
        events = knowledge_calendar_events_list(tenant_id)
    except Exception:
        current_app.logger.exception("Kalenderdaten konnten nicht geladen werden")
        events = []
    return render_template("calendar.html", events=events)

@bp.route("/calendar/export.ics")
@login_required
def export_calendar_ics():
    tenant_id = current_tenant() or session.get("tenant_id") or "default"
    feed_info = knowledge_ics_build_local_feed(tenant_id)
    feed_path = Path(str(feed_info["feed_path"]))
    ics_content = feed_path.read_bytes()
    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename={feed_info.get('feed_filename', 'calendar.ics')}"
        },
    )
