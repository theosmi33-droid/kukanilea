from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from app.auth import login_required
from app.web import _render_base, _render_sovereign_tool, _is_hx_partial_request
from app.ai.intent_analyzer import detect_write_intent
from app.security.gates import detect_injection
from app.security import csrf_protected
from app.rate_limit import chat_limiter
from app.agents.orchestrator import answer as agent_answer

logger = logging.getLogger("kukanilea.messenger")
bp = Blueprint("messenger", __name__)

WRITE_ACTIONS = {"create_task", "create_appointment", "mail_generate", "messenger_send", "mail_send"}


def _audit_chat_event(action: str, target: str = "/api/chat", meta: dict[str, Any] | None = None) -> None:
    try:
        from app import core
        from app.auth import current_role, current_tenant, current_user

        audit_log = getattr(core, "audit_log", None)
        if callable(audit_log):
            audit_log(
                user=str(current_user() or ""),
                role=str(current_role() or "USER"),
                action=action,
                target=target,
                meta=meta or {},
                tenant_id=current_tenant(),
            )
    except Exception:
        logger.debug("audit_log_unavailable", exc_info=True)


@bp.route("/messenger")
@login_required
def messenger_page():
    if _is_hx_partial_request():
        return _render_sovereign_tool(
            "messenger",
            "Messenger",
            "Messenger wird geladen...",
            active_tab="messenger",
        )
    return _render_base("messenger.html", active_tab="messenger")


@bp.route("/api/messenger/summary", methods=["GET"])
@login_required
def api_messenger_summary():
    return jsonify(
        tool="messenger",
        status="ok",
        updated_at="runtime",
        metrics={"confirm_gate": 1, "channels": 4},
        details={
            "chat_endpoint": "/api/chat",
            "confirm_gate": True,
            "message_fields": ["q", "message", "msg"],
        },
    )


def _enforce_confirm_gate(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions or []:
        item = dict(action)
        if item.get("type") in WRITE_ACTIONS:
            item["confirm_required"] = True
            item["requires_confirm"] = True
        out.append(item)
    return out


@bp.route("/api/chat", methods=["POST"])
@login_required
@csrf_protected
@chat_limiter.limit_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    msg = (payload.get("q") or payload.get("message") or payload.get("msg") or "").strip()
    if not msg:
        return jsonify(error="empty_message"), 400

    injection_pattern = detect_injection(msg)
    if injection_pattern:
        _audit_chat_event("chat_injection_blocked", meta={"pattern": injection_pattern})
        return jsonify(error="injection_blocked"), 400

    try:
        ans = agent_answer(msg)
        if isinstance(ans, dict):
            actions = _enforce_confirm_gate(ans.get("actions", []))
            write_intent = detect_write_intent(msg)
            if write_intent:
                actions = _enforce_confirm_gate(actions)
                _audit_chat_event("chat_confirm_required", meta={"write_intent": True, "action_count": len(actions)})
            ans["actions"] = actions
            if write_intent:
                ans["requires_confirm"] = True
            if "text" in ans and "response" not in ans:
                ans["response"] = ans.get("text", "")
        return jsonify(ans)
    except Exception as e:
        logger.exception("Chat logic failed")
        return jsonify(error="agent_error", details=str(e)), 500
