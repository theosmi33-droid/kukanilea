from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request, current_app, Response

from app.auth import login_required, current_tenant
from app.web import _render_base, _render_sovereign_tool, _is_hx_partial_request
from app.security import csrf_protected
from app.agents.mail import mail_agent_draft

logger = logging.getLogger("kukanilea.email")
bp = Blueprint("email", __name__)

@bp.route("/email")
@login_required
def email_page():
    if _is_hx_partial_request():
        return _render_sovereign_tool(
            "email",
            "Email-Postfach",
            "Email-System wird synchronisiert...",
            active_tab="email",
        )
    return _render_base("messenger.html", active_tab="email")

@bp.route("/api/mail/draft", methods=["POST"])
@login_required
@csrf_protected
def api_mail_draft():
    payload = request.get_json(silent=True) or {}
    try:
        draft = mail_agent_draft(payload)
        return jsonify(ok=True, draft=draft)
    except Exception as e:
        return jsonify(error="draft_error", details=str(e)), 500
