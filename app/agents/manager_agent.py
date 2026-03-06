from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.ai.intent_analyzer import detect_write_intent
from app.contracts.tool_contracts import normalize_chat_response
from app.security.untrusted_input import assess_untrusted_input

CRITICAL_PREFIXES = ("create_", "delete_", "update_", "send_", "mail_", "messenger_")
CRITICAL_ACTIONS = {"create_task", "create_appointment", "mail_send", "messenger_send", "mail_generate"}


@dataclass
class ManagerAgentResult:
    response: dict[str, Any]
    conversation_entry: dict[str, Any]


def _is_critical_action(action: dict[str, Any]) -> bool:
    action_type = str(action.get("type") or "")
    return bool(action_type in CRITICAL_ACTIONS or action_type.startswith(CRITICAL_PREFIXES))


def _extract_refs(response: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {"task_id": [], "event_id": [], "email_id": []}

    def _collect(obj: Any) -> None:
        if isinstance(obj, dict):
            for key in refs:
                value = obj.get(key)
                if value not in (None, ""):
                    refs[key].append(str(value))
            for value in obj.values():
                _collect(value)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(response)
    _collect(actions)
    return {k: sorted(set(v)) for k, v in refs.items() if v}


def _build_plan(response: dict[str, Any], actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    trace = (((response.get("data") or {}).get("hub") or {}).get("react_trace") or [])
    for idx, item in enumerate(trace, start=1):
        action = str(item.get("action") or "Analyse")
        plan.append({"step": f"{idx}. {action}", "status": "completed" if item.get("observation") else "in_progress"})

    if not plan:
        plan.append({"step": "1. Anfrage analysieren", "status": "completed"})
    if actions:
        for idx, action in enumerate(actions, start=len(plan) + 1):
            plan.append({"step": f"{idx}. Aktion vorschlagen: {action.get('type', 'unknown')}", "status": "pending"})
    else:
        plan.append({"step": f"{len(plan) + 1}. Antwort ausgeben", "status": "completed"})
    return plan


def route_via_manager_agent(
    message: str,
    *,
    role: str,
    answer_fn: Callable[..., dict[str, Any]],
) -> ManagerAgentResult:
    assessment = assess_untrusted_input(message)
    if assessment.decision in {"block", "route_to_review"}:
        blocked_response = {
            "ok": False,
            "text": "Sicherheitsprüfung aktiv: Anfrage wurde gestoppt und zur Prüfung markiert.",
            "response": "Sicherheitsprüfung aktiv: Anfrage wurde gestoppt und zur Prüfung markiert.",
            "actions": [],
            "requires_confirm": False,
            "manager_agent": {
                "route": "manager_agent",
                "proposed_actions": [],
                "plan": [{"step": "1. Sicherheitsprüfung", "status": "completed"}],
                "progress": {"total_steps": 1, "completed_steps": 1, "in_progress_step": ""},
                "object_refs": {},
            },
            "guardrail": {
                "decision": assessment.decision,
                "risk_score": assessment.risk_score,
                "signals": list(assessment.matched_signals),
                "reasons": list(assessment.reasons),
            },
        }
        return ManagerAgentResult(
            response=blocked_response,
            conversation_entry={
                "user_message": message,
                "assistant_text": blocked_response["text"],
                "requires_confirm": False,
                "proposed_actions": [],
                "plan": blocked_response["manager_agent"]["plan"],
                "object_refs": {},
                "guardrail": blocked_response["guardrail"],
            },
        )

    try:
        raw = answer_fn(message, role=role)
    except TypeError:
        raw = answer_fn(message)
    response = normalize_chat_response(raw)
    actions = [dict(a) for a in (response.get("actions") or []) if isinstance(a, dict)]

    write_intent = detect_write_intent(message)
    critical_actions = [_is_critical_action(action) for action in actions]
    requires_confirm = bool(response.get("requires_confirm") or write_intent or any(critical_actions))

    for idx, action in enumerate(actions):
        action["confirm_required"] = bool(action.get("confirm_required") or critical_actions[idx] or requires_confirm)
        action["proposed"] = True

    plan = _build_plan(response, actions)
    progress = {
        "total_steps": len(plan),
        "completed_steps": sum(1 for item in plan if item.get("status") == "completed"),
        "in_progress_step": next((item.get("step") for item in plan if item.get("status") == "in_progress"), ""),
    }

    refs = _extract_refs(response, actions)
    response["actions"] = actions
    response["requires_confirm"] = requires_confirm
    response["manager_agent"] = {
        "route": "manager_agent",
        "proposed_actions": actions,
        "plan": plan,
        "progress": progress,
        "object_refs": refs,
    }

    return ManagerAgentResult(
        response=response,
        conversation_entry={
            "user_message": message,
            "assistant_text": response.get("text", ""),
            "requires_confirm": requires_confirm,
            "proposed_actions": actions,
            "plan": plan,
            "object_refs": refs,
        },
    )
