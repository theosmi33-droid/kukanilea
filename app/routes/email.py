from __future__ import annotations

import logging
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from app.auth import current_tenant, current_user, login_required
from app.modules.mail.contracts import build_health as build_mail_health
from app.modules.mail.contracts import build_summary as build_mail_summary
from app.modules.mail.logic import classify_message, generate_reply_draft
from app.modules.mail.postfach import (
    EmailpostfachService,
    ProviderAuthError,
    ProviderNetworkError,
    StubInboxProvider,
)
from app.security import csrf_protected
from app.web import _is_hx_partial_request, _render_base, _render_sovereign_tool

logger = logging.getLogger("kukanilea.email")
bp = Blueprint("email", __name__)


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _sla_hours_arg(default: int = 24) -> int:
    raw = request.args.get("sla_hours", default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _postfach_service() -> EmailpostfachService:
    auth_db = current_app.extensions["auth_db"]

    def provider_factory(provider_name: str):
        name = str(provider_name or "imap_stub").lower()
        if name in {"imap", "imap_stub"}:
            return StubInboxProvider(name="imap_stub", mode="ok")
        if name in {"pop", "pop3", "pop_stub"}:
            return StubInboxProvider(name="pop_stub", mode="ok")
        if name in {"smtp_intake", "smtp_stub"}:
            return StubInboxProvider(name="smtp_stub", mode="ok")
        if name == "auth_fail":
            return StubInboxProvider(name="imap_stub", mode="auth_fail")
        if name == "network_fail":
            return StubInboxProvider(name="imap_stub", mode="network_fail")
        return StubInboxProvider(name=name, mode="ok")

    return EmailpostfachService(db_path=str(auth_db.path), inbox_provider_factory=provider_factory)

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
    payload = _json_object_payload()
    try:
        message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
        draft = generate_reply_draft(message, read_only_default=True, external_api_enabled=False)
        return jsonify(ok=True, draft=draft)
    except Exception:
        logger.exception("api_mail_draft_failed")
        return jsonify(error="draft_error"), 500


@bp.route("/api/mail/triage", methods=["POST"])
@login_required
@csrf_protected
def api_mail_triage():
    payload = _json_object_payload()
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    result = classify_message(message)
    return jsonify(ok=True, triage=result.__dict__)


@bp.route("/api/mail/draft/generate", methods=["POST"])
@login_required
@csrf_protected
def api_mail_draft_generate():
    payload = _json_object_payload()
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    draft = generate_reply_draft(message, read_only_default=True, external_api_enabled=False)
    return jsonify(ok=True, draft=draft)


@bp.route("/api/mail/summary", methods=["GET"])
@login_required
def api_mail_summary():
    tenant = str(current_tenant() or "default")
    sla_hours = _sla_hours_arg()
    return jsonify(build_mail_summary(tenant, messages=[], sla_hours=sla_hours))


@bp.route("/api/mail/health", methods=["GET"])
@login_required
def api_mail_health():
    tenant = str(current_tenant() or "default")
    sla_hours = _sla_hours_arg()
    payload, code = build_mail_health(tenant, messages=[], sla_hours=sla_hours)
    return jsonify(payload), code


@bp.route("/api/emailpostfach/summary", methods=["GET"])
@login_required
def api_emailpostfach_summary():
    tenant = str(current_tenant() or "default")
    try:
        return jsonify(_postfach_service().summary(tenant_id=tenant))
    except (sqlite3.Error, RuntimeError):
        logger.exception("api_emailpostfach_summary_runtime_unavailable")
        return (
            jsonify(
                tool="emailpostfach",
                status="degraded",
                degraded_reason="email_runtime_unavailable",
                metrics={"unread_count": 0, "follow_ups_due": 0},
                last_sync="",
            ),
            503,
        )


@bp.route("/api/emailpostfach/health", methods=["GET"])
@login_required
def api_emailpostfach_health():
    tenant = str(current_tenant() or "default")
    try:
        summary = _postfach_service().summary(tenant_id=tenant)
        return jsonify(tool="emailpostfach", status="ok", checks={"summary_runtime": True}, summary=summary), 200
    except (sqlite3.Error, RuntimeError):
        logger.exception("api_emailpostfach_health_runtime_unavailable")
        return (
            jsonify(
                tool="emailpostfach",
                status="degraded",
                degraded_reason="email_runtime_unavailable",
                checks={"summary_runtime": False},
            ),
            503,
        )


@bp.route("/api/emailpostfach/ingest", methods=["POST"])
@login_required
@csrf_protected
def api_emailpostfach_ingest():
    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider") or "imap_stub")
    actor = str(current_user() or "system")
    tenant = str(current_tenant() or "default")
    service = _postfach_service()
    try:
        result = service.ingest(tenant_id=tenant, provider_name=provider, actor=actor)
        return jsonify(ok=True, result=result)
    except ProviderNetworkError as exc:
        return jsonify(ok=False, error=str(exc), provider=provider), 503
    except ProviderAuthError as exc:
        return jsonify(ok=False, error=str(exc), provider=provider), 401


@bp.route("/api/emailpostfach/draft/generate", methods=["POST"])
@login_required
@csrf_protected
def api_emailpostfach_draft_generate():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    actor = str(current_user() or "system")
    use_llm = bool(payload.get("use_llm", False))
    tenant = str(current_tenant() or "default")
    draft = _postfach_service().create_draft(
        tenant_id=tenant,
        actor=actor,
        message=message if isinstance(message, dict) else {},
        use_llm=use_llm,
    )
    return jsonify(ok=True, draft=draft)


@bp.route("/api/emailpostfach/draft/<draft_id>/edit", methods=["POST"])
@login_required
@csrf_protected
def api_emailpostfach_draft_edit(draft_id: str):
    payload = request.get_json(silent=True) or {}
    actor = str(current_user() or "system")
    subject = str(payload.get("subject") or "")
    body = str(payload.get("body") or "")
    tenant = str(current_tenant() or "default")
    try:
        result = _postfach_service().edit_draft(
            tenant_id=tenant,
            actor=actor,
            draft_id=draft_id,
            subject=subject,
            body=body,
        )
    except KeyError:
        return jsonify(ok=False, error="draft_not_found"), 404
    return jsonify(ok=True, result=result)


@bp.route("/api/emailpostfach/draft/<draft_id>/send", methods=["POST"])
@login_required
@csrf_protected
def api_emailpostfach_send(draft_id: str):
    payload = request.get_json(silent=True) or {}
    actor = str(current_user() or "system")
    confirm = str(payload.get("confirm") or "").strip().lower() in {"yes", "true", "1", "y"}
    tenant = str(current_tenant() or "default")
    try:
        result = _postfach_service().send_draft(tenant_id=tenant, actor=actor, draft_id=draft_id, confirm=confirm)
    except KeyError:
        return jsonify(ok=False, error="draft_not_found"), 404
    status_code = 200 if result.get("status") == "sent" else 409
    return jsonify(ok=result.get("status") == "sent", result=result), status_code
