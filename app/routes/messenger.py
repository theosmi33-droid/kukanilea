from __future__ import annotations
import logging
import json
from flask import Blueprint, jsonify, request, current_app

from app.auth import login_required, current_tenant, current_user
from app.web import _render_base, _render_sovereign_tool, _is_hx_partial_request
from app.security import csrf_protected
from app.rate_limit import chat_limiter
from app.agents.orchestrator import answer as agent_answer

logger = logging.getLogger("kukanilea.messenger")
bp = Blueprint("messenger", __name__)

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

@bp.route("/api/chat", methods=["POST"])
@login_required
@csrf_protected
@chat_limiter.limit_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    msg = (payload.get("q") or payload.get("message") or "").strip()
    if not msg:
        return jsonify(error="empty_message"), 400
    
    tenant_id = str(current_tenant() or "default")
    user = str(current_user() or "dev")
    
    try:
        # Optimization: Competition-level agent handling
        ans = agent_answer(msg, tenant_id=tenant_id, user=user)
        return jsonify(ok=True, answer=ans)
    except Exception as e:
        logger.exception("Chat logic failed")
        return jsonify(error="agent_error", details=str(e)), 500
