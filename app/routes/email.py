from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request, current_app, Response

from app.auth import login_required, current_tenant
from app.web import _render_base, _render_sovereign_tool, _is_hx_partial_request
from app.security import csrf_protected
from app.agents.mail import mail_agent_draft
from app.modules.mail.logic import classify_message, generate_reply_draft
from app.modules.mail.contracts import build_summary as build_mail_summary
from app.modules.mail.contracts import build_health as build_mail_health

logger = logging.getLogger("kukanilea.email")
bp = Blueprint("email", __name__)

@bp.route("/email")
@login_required
def email_page():
    if _is_hx_partial_request():
        return _render_sovereign_tool(
            "email",
            "Email-Postfach",
            "Email-Cockpit wird vorbereitet...",
            active_tab="email",
        )
    return _render_base("email.html", active_tab="email")

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


@bp.route("/api/mail/triage", methods=["POST"])
@login_required
@csrf_protected
def api_mail_triage():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    result = classify_message(message)
    return jsonify(ok=True, triage=result.__dict__)


@bp.route("/api/mail/draft/generate", methods=["POST"])
@login_required
@csrf_protected
def api_mail_draft_generate():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    draft = generate_reply_draft(message, read_only_default=True, external_api_enabled=False)
    return jsonify(ok=True, draft=draft)


@bp.route("/api/mail/summary", methods=["GET"])
@login_required
def api_mail_summary():
    tenant = str(current_tenant() or "default")
    sla_hours = int(request.args.get("sla_hours", 24))
    return jsonify(build_mail_summary(tenant, messages=[], sla_hours=sla_hours))


@bp.route("/api/mail/health", methods=["GET"])
@login_required
def api_mail_health():
    tenant = str(current_tenant() or "default")
    sla_hours = int(request.args.get("sla_hours", 24))
    payload, code = build_mail_health(tenant, messages=[], sla_hours=sla_hours)
    return jsonify(payload), code
