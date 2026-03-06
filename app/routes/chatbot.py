from __future__ import annotations
import logging
import re
import time
from typing import Any, Dict, List, Optional
from flask import Blueprint, jsonify, request, session, current_app
from app.auth import login_required, current_tenant, current_user
from app.security import csrf_protected
from app.contracts.tool_contracts import (
    build_tool_health, 
    build_tool_summary,
    extract_chat_message,
    normalize_chat_response
)
from app.core.orchestrator import Orchestrator
from app import core
from app.modules.observability.metrics import increment_counter
from app.modules.weather.logic import get_weather

logger = logging.getLogger("kukanilea.chatbot")
bp = Blueprint("chatbot", __name__)

def _weather_answer(city: str) -> str:
    info = get_weather(city)
    if not info:
        return f"Ich konnte das Wetter für {city} nicht abrufen."
    return f"Wetter {info.get('city', '')}: {info.get('summary', '')} (Temp: {info.get('temp_c', '?')}°C, Wind: {info.get('wind_kmh', '?')} km/h)"

def _weather_adapter(message: str) -> str:
    city = "Berlin"
    match = re.search(r"\bin\s+([A-Za-zÄÖÜäöüß\- ]{2,40})\b", message, re.IGNORECASE)
    if match:
        city = match.group(1).strip()
    return _weather_answer(city)

ORCHESTRATOR = Orchestrator(core, weather_adapter=_weather_adapter)

_WIDGET_READONLY_ACTIONS = {
    "search_docs",
    "open_token",
    "show_customer",
    "summarize_doc",
    "list_tasks",
    "memory_search",
}

def _widget_requires_confirm(actions: List[Dict[str, Any]]) -> bool:
    for action in actions:
        action_type = str(action.get("type", "")).strip().lower()
        if action_type and action_type not in _WIDGET_READONLY_ACTIONS:
            return True
    return False

def _mark_actions_confirm_required(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    marked: List[Dict[str, Any]] = []
    for action in actions or []:
        item = dict(action)
        item["requires_confirm"] = True
        item["confirm_required"] = True
        marked.append(item)
    return marked

def _widget_compact_response(
    *,
    text: str,
    model: str,
    context_tag: str,
    latency_ms: int,
    suggestions: List[str] | None = None,
    actions: List[Dict[str, Any]] | None = None,
    thinking_steps: List[str] | None = None,
    requires_confirm: bool = False,
    pending_id: str = "",
    confirm_prompt: str = "",
    pending_approvals: List[Dict[str, Any]] | None = None,
    status: str = "Bereit",
    ok: bool = True,
) -> Dict[str, Any]:
    return {
        "ok": ok,
        "text": text,
        "response": text,
        "model": model,
        "current_context": context_tag,
        "status": status,
        "latency_ms": int(latency_ms),
        "suggestions": suggestions or [],
        "actions": actions or [],
        "thinking_steps": thinking_steps or [],
        "requires_confirm": bool(requires_confirm),
        "pending_id": pending_id,
        "confirm_prompt": confirm_prompt,
        "pending_approvals": pending_approvals or [],
    }

def _get_widget_pending_queue() -> List[Dict[str, Any]]:
    queue = session.get("widget_pending_actions")
    if isinstance(queue, list):
        return [item for item in queue if isinstance(item, dict)]
    legacy = session.get("widget_pending_action")
    if isinstance(legacy, dict) and legacy.get("id"):
        return [legacy]
    return []

WIDGET_PENDING_QUEUE_LIMIT = 5
WIDGET_PENDING_ACTION_PREVIEW_LIMIT = 3

def _compact_pending_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compact: List[Dict[str, Any]] = []
    for action in actions[:WIDGET_PENDING_ACTION_PREVIEW_LIMIT]:
        if not isinstance(action, dict):
            continue
        compact.append(
            {
                "type": str(action.get("type") or action.get("name") or "action"),
                "label": str(action.get("label") or action.get("type") or action.get("name") or "Aktion"),
                "confirm_required": bool(action.get("confirm_required")),
            }
        )
    return compact

def _set_widget_pending_queue(queue: List[Dict[str, Any]]) -> None:
    normalized = [item for item in queue if isinstance(item, dict)]
    session["widget_pending_actions"] = normalized[-WIDGET_PENDING_QUEUE_LIMIT:]
    session.pop("widget_pending_action", None)
    session.modified = True

def _serialize_pending_approvals(queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for item in queue:
        pending_id = str(item.get("id") or "").strip()
        if not pending_id:
            continue
        actions = item.get("actions") if isinstance(item.get("actions"), list) else []
        serialized.append(
            {
                "pending_id": pending_id,
                "current_context": str(item.get("current_context") or "/"),
                "confirm_prompt": str(item.get("confirm_prompt") or "Bestätigung erforderlich."),
                "action_count": len(actions),
            }
        )
    return serialized

@bp.route("/api/chat", methods=["POST"])
@login_required
@csrf_protected
def api_chat():
    start = time.time()
    payload = request.get_json(silent=True) or {}
    q = extract_chat_message(payload)
    if not q:
        return jsonify(error="empty_query"), 400

    tenant = str(current_tenant() or "default")
    increment_counter("chat_requests_total", labels={"tenant": tenant})
    
    result = ORCHESTRATOR.ask(
        q, 
        tenant_id=tenant, 
        user=current_user() or "system",
        context_tag=str(payload.get("context_tag") or "/")
    )
    
    latency = int((time.time() - start) * 1000)
    response = normalize_chat_response(result)
    response["latency_ms"] = latency
    return jsonify(response)

@bp.route("/api/chat/compact", methods=["GET", "POST"])
@login_required
@csrf_protected
def api_chat_compact():
    start = time.time()
    payload = request.get_json(silent=True) or {}
    q = extract_chat_message(payload)
    if not q and request.method == "POST":
        return jsonify(error="empty_query"), 400

    tenant = str(current_tenant() or "default")
    context_tag = str(payload.get("context_tag") or "/")
    
    # Handle direct commands (confirm/reject)
    cmd = str(payload.get("command") or "").lower()
    if cmd in {"confirm", "reject"}:
        pending_id = str(payload.get("pending_id") or "").strip()
        queue = _get_widget_pending_queue()
        match = next((item for item in queue if item.get("id") == pending_id), None)
        if not match:
            return jsonify(_widget_compact_response(
                text="Aktion nicht mehr gültig oder bereits verarbeitet.",
                model="system", context_tag=context_tag, latency_ms=0, ok=False
            ))
        
        # Remove from queue
        _set_widget_pending_queue([item for item in queue if item.get("id") != pending_id])
        
        if cmd == "confirm":
            actions = match.get("actions") if isinstance(match.get("actions"), list) else []
            # In sovereign11 mode, execute actions via orchestrator
            ORCHESTRATOR.execute_actions(actions, tenant_id=tenant, user=current_user() or "system")
            return jsonify(_widget_compact_response(
                text=f"Aktion '{match.get('label', 'Anfrage')}' wurde bestätigt und ausgeführt.",
                model="system", context_tag=context_tag, latency_ms=0
            ))
        else:
            return jsonify(_widget_compact_response(
                text=f"Aktion '{match.get('label', 'Anfrage')}' wurde abgelehnt.",
                model="system", context_tag=context_tag, latency_ms=0
            ))

    # Regular chat
    result = ORCHESTRATOR.ask(
        q, 
        tenant_id=tenant, 
        user=current_user() or "system",
        context_tag=context_tag
    )
    
    latency = int((time.time() - start) * 1000)
    text = str(result.text if hasattr(result, "text") else (result.get("text") or result.get("response") or ""))
    actions = result.actions if hasattr(result, "actions") else (result.get("actions") or [])
    
    requires_confirm = _widget_requires_confirm(actions)
    pending_id = ""
    if requires_confirm:
        pending_id = f"act_{int(time.time())}"
        queue = _get_widget_pending_queue()
        queue.append({
            "id": pending_id,
            "label": q[:30] + "...",
            "actions": actions,
            "current_context": context_tag,
            "confirm_prompt": "Soll ich diese Aktion ausführen?"
        })
        _set_widget_pending_queue(queue)
        # Don't return actions yet if confirm is required
        actions = _compact_pending_actions(actions)
        
    return jsonify(_widget_compact_response(
        text=text,
        model=getattr(result, "model", "local"),
        context_tag=context_tag,
        latency_ms=latency,
        actions=actions,
        requires_confirm=requires_confirm,
        pending_id=pending_id,
        confirm_prompt="Soll ich das wirklich tun?" if requires_confirm else ""
    ))

@bp.route("/messenger")
@login_required
def messenger_page():
    from app.web import _render_base
    return _render_base("messenger.html", active_tab="messenger")

@bp.get("/api/chatbot/summary")
@login_required
def api_chatbot_summary():
    tenant = str(current_tenant() or "default")
    return jsonify(build_tool_summary("chatbot", tenant=tenant))

@bp.get("/api/chatbot/health")
@login_required
def api_chatbot_health():
    tenant = str(current_tenant() or "default")
    payload = build_tool_health("chatbot", tenant=tenant)
    code = 200 if payload.get("status") in {"ok", "degraded"} else 503
    return jsonify(payload), code
