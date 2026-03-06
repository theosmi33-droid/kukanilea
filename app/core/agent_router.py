from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.mia_audit import (
    MIA_EVENT_ACTION_SELECTED,
    MIA_EVENT_INTENT_DETECTED,
    MIA_EVENT_PARAMETER_VALIDATION_FAILED,
    MIA_EVENT_ROUTE_BLOCKED,
    canonical_mia_payload,
    emit_mia_event_safe,
)


READ_KEYWORDS = {
    "show",
    "zeige",
    "list",
    "status",
    "read",
    "find",
    "suche",
    "fetch",
}
WRITE_KEYWORDS = {
    "create",
    "erstelle",
    "update",
    "ändern",
    "aendern",
    "send",
    "sende",
    "upload",
    "add",
    "remove",
    "delete",
    "lösche",
    "loesche",
}
HIGH_RISK_KEYWORDS = {
    "drop",
    "purge",
    "destroy",
    "wipe",
    "revoke",
    "shutdown",
}


@dataclass(frozen=True)
class IntentResult:
    tool: str
    confidence: float
    needed_clarifications: list[str]



def _tokenize(message: str) -> set[str]:
    return {token.strip(".,!?;:\"'()[]{}") for token in str(message or "").lower().split() if token.strip()}



def classify_intent(message: str, audit_context: dict[str, Any] | None = None) -> dict[str, Any]:
    audit_context = audit_context or {}
    tenant_id = str(audit_context.get("tenant_id") or audit_context.get("tenant") or "KUKANILEA")
    user_id = str(audit_context.get("user_id") or "system")
    route_ref = str(audit_context.get("route_ref") or f"{tenant_id}:{user_id}:intent")
    tokens = _tokenize(message)
    if not tokens:
        emit_mia_event_safe(
            event_type=MIA_EVENT_PARAMETER_VALIDATION_FAILED,
            entity_type="agent_router",
            entity_ref=route_ref,
            tenant_id=tenant_id,
            payload=canonical_mia_payload(
                tenant_id=tenant_id,
                user_id=user_id,
                action="classify_intent",
                status="failed",
                risk="low",
                meta={"reason": "empty_message"},
            ),
        )
        return IntentResult(
            tool="clarify.intent",
            confidence=0.0,
            needed_clarifications=["Bitte beschreibe, welche Aktion ausgeführt werden soll."],
        ).__dict__

    emit_mia_event_safe(
        event_type=MIA_EVENT_INTENT_DETECTED,
        entity_type="agent_router",
        entity_ref=route_ref,
        tenant_id=tenant_id,
        payload=canonical_mia_payload(
            tenant_id=tenant_id,
            user_id=user_id,
            action="classify_intent",
            status="detected",
            risk="high" if bool(tokens & HIGH_RISK_KEYWORDS) else "low",
            meta={"token_count": len(tokens)},
        ),
    )

    has_high_risk = bool(tokens & HIGH_RISK_KEYWORDS)
    has_write = bool(tokens & WRITE_KEYWORDS)
    has_read = bool(tokens & READ_KEYWORDS)

    clarifications: list[str] = []
    if has_high_risk:
        tool = "core.high_risk_action"
        confidence = 0.93
    elif has_write and not has_read:
        tool = "core.write_action"
        confidence = 0.84
    elif has_read and not has_write:
        tool = "core.read_action"
        confidence = 0.88
    elif has_read and has_write:
        tool = "clarify.intent"
        confidence = 0.42
        clarifications.append("Soll ich nur lesen oder auch schreiben?")
    else:
        tool = "clarify.intent"
        confidence = 0.25
        clarifications.append("Welche konkrete Tool-Aktion soll ich ausführen?")

    if "tenant" not in tokens and tool != "clarify.intent":
        clarifications.append("Für welchen Tenant gilt die Aktion?")

    status = "selected"
    if tool == "clarify.intent":
        status = "blocked"
        emit_mia_event_safe(
            event_type=MIA_EVENT_ROUTE_BLOCKED,
            entity_type="agent_router",
            entity_ref=route_ref,
            tenant_id=tenant_id,
            payload=canonical_mia_payload(
                tenant_id=tenant_id,
                user_id=user_id,
                action=tool,
                status="blocked",
                risk="medium",
                meta={"clarifications": clarifications},
            ),
        )
    emit_mia_event_safe(
        event_type=MIA_EVENT_ACTION_SELECTED,
        entity_type="agent_router",
        entity_ref=route_ref,
        tenant_id=tenant_id,
        payload=canonical_mia_payload(
            tenant_id=tenant_id,
            user_id=user_id,
            action=tool,
            status=status,
            risk="high" if tool == "core.high_risk_action" else "low",
            meta={"confidence": confidence},
        ),
    )

    return IntentResult(tool=tool, confidence=confidence, needed_clarifications=clarifications).__dict__



def plan_actions(message: str, context: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    context = context or {}
    intent = classify_intent(message, context)
    steps: list[dict[str, Any]] = []

    if intent["tool"] == "clarify.intent":
        steps.append(
            {
                "id": "step-clarify",
                "tool": "clarify.intent",
                "action_type": "read",
                "message": "Klärung erforderlich",
                "questions": intent["needed_clarifications"],
            }
        )
        return {"steps": steps}

    action_type = "read"
    if intent["tool"] == "core.write_action":
        action_type = "write"
    elif intent["tool"] == "core.high_risk_action":
        action_type = "high_risk"

    steps.append(
        {
            "id": "step-1",
            "tool": intent["tool"],
            "action_type": action_type,
            "params": {
                "message": message,
                "tenant": context.get("tenant"),
                "user_id": context.get("user_id"),
            },
            "needed_clarifications": intent["needed_clarifications"],
        }
    )

    return {"steps": steps}
