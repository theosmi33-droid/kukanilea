from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from app.auth import login_required
from app.web import _render_base, _render_sovereign_tool, _is_hx_partial_request
from app.security import csrf_protected
from app.rate_limit import chat_limiter
from app.agents.orchestrator import answer as agent_answer

logger = logging.getLogger("kukanilea.messenger")
bp = Blueprint("messenger", __name__)

WRITE_ACTIONS = {"create_task", "create_appointment", "mail_generate", "messenger_send", "mail_send"}


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
        ok=True,
        domain="messenger",
        summary={
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

    try:
        ans = agent_answer(msg)
        if isinstance(ans, dict):
            ans["actions"] = _enforce_confirm_gate(ans.get("actions", []))
            if "text" in ans and "response" not in ans:
                ans["response"] = ans.get("text", "")
        return jsonify(ans)
    except Exception as e:
        logger.exception("Chat logic failed")
        return jsonify(error="agent_error", details=str(e)), 500
