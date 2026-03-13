from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, current_app, render_template, session

from app.auth import current_tenant, login_required
from app.knowledge.ics_source import (
    knowledge_calendar_events_list,
    knowledge_ics_build_local_feed,
)

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
    try:
        feed_info = knowledge_ics_build_local_feed(tenant_id)
        feed_path = Path(str(feed_info.get("feed_path") or "")).expanduser()
        ics_content = feed_path.read_bytes() if feed_path.exists() else b""
    except ValueError as exc:
        if str(exc) != "policy_blocked":
            raise
        current_app.logger.info(
            "ICS export blocked by knowledge policy", extra={"tenant_id": tenant_id}
        )
        ics_content = b""
    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=calendar.ics"}
    )
