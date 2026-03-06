from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from app.auth import current_tenant, login_required
from app.web import _is_hx_partial_request, _render_base, _render_sovereign_tool
from app.contracts.tool_contracts import build_tool_summary, extract_chat_message, normalize_chat_response
from app.ai.intent_analyzer import detect_standard_request, detect_write_intent
from app.ai.guardrails import validate_prompt
from app.security.gates import detect_injection
from app.security import csrf_protected
from app.rate_limit import chat_limiter
from app.agents.orchestrator import answer as agent_answer
from app.modules.messenger import parse_chat_intake

logger = logging.getLogger("kukanilea.messenger")
bp = Blueprint("messenger", __name__)

WRITE_ACTIONS = {"create_task", "create_appointment", "mail_generate", "messenger_send", "mail_send"}
WRITE_PREFIXES = ("create_", "delete_", "update_", "send_", "mail_", "messenger_")


def _summary_context() -> dict[str, Any]:
    tenant = current_tenant() or "default"
    keys = ("dashboard", "tasks", "projects")
    return {name: build_tool_summary(name, tenant=tenant) for name in keys}


def _read_only_fallback(message: str, *, reason: str = "fallback") -> dict[str, Any]:
    summaries = _summary_context()
    tasks_open = summaries["tasks"].get("metrics", {}).get("tasks_open", 0)
    projects_total = summaries["projects"].get("metrics", {}).get("total_projects", 0)
    text = (
        "Ich habe dafür aktuell keine präzise Aktion gefunden, kann aber read-only helfen: "
        f"{tasks_open} offene Tasks, {projects_total} Projekte. "
        "Frage z.B. nach Aufgabenstatus, Projektübersicht oder Dashboard-Status."
    )
    return {
        "ok": True,
        "text": text,
        "response": text,
        "actions": [],
        "requires_confirm": False,
        "data": {"reason": reason, "tool_summaries": summaries, "message": message[:200]},
    }


def _standard_response(kind: str) -> dict[str, Any] | None:
    summaries = _summary_context()
    if kind == "greeting":
        text = "Hallo! Ich bin bereit. Ich kann dir Dashboard-, Task- und Projektstände direkt zusammenfassen."
    elif kind == "self_test":
        text = "Ja, ich funktioniere. Frag mich z.B. nach offenen Tasks, Projektstatus oder Dashboard-Zustand."
    else:
        return None
    return {
        "ok": True,
        "text": text,
        "response": text,
        "actions": [],
        "requires_confirm": False,
        "data": {"tool_summaries": summaries, "request_kind": kind},
    }


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
    return jsonify(build_tool_summary("messenger", tenant=current_tenant() or "default"))


def _enforce_confirm_gate(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for action in actions or []:
        item = dict(action)
        action_type = str(item.get("type") or "")
        is_write = action_type in WRITE_ACTIONS or action_type.startswith(WRITE_PREFIXES)
        if is_write:
            item["confirm_required"] = True
            item["requires_confirm"] = True
        out.append(item)
    return out


def _collect_confirm_gate_logs(actions: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_actions: list[dict[str, Any]] = []
    confirm_required_actions: list[dict[str, Any]] = []
    for action in actions:
        action_type = str(action.get("type") or "")
        if not action_type:
            continue
        if bool(action.get("confirm_required") or action.get("requires_confirm")):
            confirm_required_actions.append({"type": action_type, "reason": "confirm_gate"})
            blocked_actions.append({"type": action_type, "reason": "awaiting_explicit_confirm"})
            _audit_chat_event("chat_confirm_required_action", meta={"action": action_type, "blocked": True})
    return {
        "confirm_required_actions": confirm_required_actions,
        "blocked_actions": blocked_actions,
    }


@bp.route("/api/chat", methods=["POST"])
@login_required
@csrf_protected
@chat_limiter.limit_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    msg = extract_chat_message(payload if isinstance(payload, dict) else {})
    if not msg:
        return jsonify(error="empty_message"), 400

    injection_pattern = detect_injection(msg)
    if injection_pattern:
        _audit_chat_event("chat_injection_blocked", meta={"pattern": injection_pattern})
        return jsonify(error="injection_blocked"), 400

    valid, guard_reason = validate_prompt(msg)
    if not valid:
        _audit_chat_event("chat_guardrails_blocked", meta={"reason": guard_reason})
        return jsonify(error="injection_blocked", reason=guard_reason), 400

    standard_kind = detect_standard_request(msg)
    if standard_kind:
        _audit_chat_event("chat_standard_request", meta={"kind": standard_kind})
        return jsonify(_standard_response(standard_kind))

    try:
        ans = normalize_chat_response(agent_answer(msg))
        if (not ans.get("text")) or "keine treffer" in ans.get("text", "").lower():
            _audit_chat_event("chat_readonly_fallback", meta={"reason": "empty_or_no_hits"})
            return jsonify(_read_only_fallback(msg, reason="empty_or_no_hits"))
        actions = _enforce_confirm_gate(ans.get("actions", []))
        write_intent = detect_write_intent(msg)
        intake = parse_chat_intake(msg, actions)
        if write_intent:
            actions = _enforce_confirm_gate(actions)
            _audit_chat_event("chat_confirm_required", meta={"write_intent": True, "action_count": len(actions)})
        ans["actions"] = actions
        if write_intent:
            ans["requires_confirm"] = True
        ans.setdefault("data", {})
        if isinstance(ans["data"], dict):
            ans["data"].setdefault("tool_summaries", _summary_context())
            ans["data"]["intake"] = intake
            ans["data"]["policy_events"] = _collect_confirm_gate_logs(actions)
        return jsonify(ans)
    except Exception:
        logger.exception("Chat logic failed")
        _audit_chat_event("chat_readonly_fallback", meta={"reason": "agent_exception"})
        return jsonify(_read_only_fallback(msg, reason="agent_exception")), 200
