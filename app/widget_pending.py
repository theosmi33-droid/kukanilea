from __future__ import annotations

from typing import Any, Dict, List

from flask import session

WIDGET_PENDING_QUEUE_LIMIT = 5
WIDGET_PENDING_ACTION_PREVIEW_LIMIT = 3

_WIDGET_READONLY_ACTIONS = {
    "search_docs",
    "open_token",
    "show_customer",
    "summarize_doc",
    "list_tasks",
    "memory_search",
}


def widget_requires_confirm(actions: List[Dict[str, Any]]) -> bool:
    for action in actions:
        action_type = str(action.get("type", "")).strip().lower()
        if action_type and action_type not in _WIDGET_READONLY_ACTIONS:
            return True
    return False


def mark_actions_confirm_required(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    marked: List[Dict[str, Any]] = []
    for action in actions or []:
        item = dict(action)
        item["requires_confirm"] = True
        item["confirm_required"] = True
        marked.append(item)
    return marked


def get_widget_pending_queue() -> List[Dict[str, Any]]:
    queue = session.get("widget_pending_actions")
    if isinstance(queue, list):
        return [item for item in queue if isinstance(item, dict)]
    legacy = session.get("widget_pending_action")
    if isinstance(legacy, dict) and legacy.get("id"):
        return [legacy]
    return []


def compact_pending_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def set_widget_pending_queue(queue: List[Dict[str, Any]]) -> None:
    normalized = [item for item in queue if isinstance(item, dict)]
    session["widget_pending_actions"] = normalized[-WIDGET_PENDING_QUEUE_LIMIT:]
    session.pop("widget_pending_action", None)
    session.modified = True


def serialize_pending_approvals(queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
