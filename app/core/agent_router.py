from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from app.tools.action_registry import action_registry


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
    action_name: str | None
    confidence: float
    needed_clarifications: list[str]


def _tokenize(message: str) -> set[str]:
    return {token.strip(".,!?;:\"'()[]{}") for token in str(message or "").lower().split() if token.strip()}


def classify_intent(message: str) -> dict[str, Any]:
    tokens = _tokenize(message)
    if not tokens:
        return IntentResult(
            tool="clarify.intent",
            action_name=None,
            confidence=0.0,
            needed_clarifications=["Bitte beschreibe, welche Aktion ausgeführt werden soll."],
        ).__dict__

    # 1. Action Registry Lookup (New hierarchical discovery)
    best_action = None
    max_matches = 0
    
    # Map common synonyms to parts of the hierarchy
    synonyms = {
        "mail": {"emailpostfach", "mail"},
        "email": {"emailpostfach", "mail"},
        "postfach": {"emailpostfach"},
        "nachricht": {"messenger", "chat"},
        "chat": {"messenger", "chat"},
        "datei": {"upload", "filesystem"},
        "file": {"upload", "filesystem"},
        "aufgabe": {"aufgaben", "workitem"},
        "task": {"aufgaben", "workitem"},
        "termin": {"kalender", "appointment"},
        "rechnung": {"upload", "zugferd", "lexoffice"},
        "invoice": {"upload", "zugferd", "lexoffice"},
        # Verb synonyms
        "sende": {"send"},
        "schicke": {"send"},
        "erstelle": {"create"},
        "neu": {"create"},
        "lösche": {"delete"},
        "entferne": {"delete"},
        "ändere": {"update"},
        "suche": {"search", "read"},
    }

    # Expand tokens with synonyms for better matching
    expanded_tokens = set(tokens)
    for t in tokens:
        if t in synonyms:
            expanded_tokens.update(synonyms[t])

    for name in action_registry._actions_by_name.keys():
        name_parts = name.lower().split(".")
        # Heuristic: 
        # - Domain/Entity match = 1 point each
        # - Verb (last part) match = 2 points (crucial for distinguishing CREATE vs SEND)
        score = 0
        for i, part in enumerate(name_parts):
            if part in expanded_tokens:
                score += 2 if i == len(name_parts) - 1 else 1
        
        if score > max_matches:
            max_matches = score
            best_action = name

    if best_action and max_matches >= 3:  # Expect at least Entity/Domain + Verb or multiple parts
        action_def = action_registry._actions_by_name[best_action]
        return IntentResult(
            tool=action_def.tool_name,
            action_name=best_action,
            confidence=0.9,
            needed_clarifications=[],
        ).__dict__

    # 2. Fallback to keyword-based categories
    has_high_risk = bool(tokens & HIGH_RISK_KEYWORDS)
    has_write = bool(tokens & WRITE_KEYWORDS)
    has_read = bool(tokens & READ_KEYWORDS)

    clarifications: list[str] = []
    if has_high_risk:
        tool = "core.high_risk_action"
        confidence = 0.7  # Lowered because generic
    elif has_write and not has_read:
        tool = "core.write_action"
        confidence = 0.6
    elif has_read and not has_write:
        tool = "core.read_action"
        confidence = 0.6
    else:
        tool = "clarify.intent"
        confidence = 0.2
        clarifications.append("Welche konkrete Tool-Aktion soll ich ausführen?")

    if "tenant" not in tokens and tool != "clarify.intent":
        clarifications.append("Für welchen Tenant gilt die Aktion?")

    return IntentResult(tool=tool, action_name=None, confidence=confidence, needed_clarifications=clarifications).__dict__


def plan_actions(message: str, context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    intent = classify_intent(message)
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

    action_name = intent.get("action_name")
    action_type = "read"
    
    if action_name:
        # Determine type from registry metadata
        action_def = action_registry._actions_by_name[action_name]
        if action_def.is_critical:
            action_type = "high_risk"
        elif action_def.risk_level == "MEDIUM":
            action_type = "write"
    else:
        if intent["tool"] == "core.write_action":
            action_type = "write"
        elif intent["tool"] == "core.high_risk_action":
            action_type = "high_risk"

    steps.append(
        {
            "id": "step-1",
            "tool": action_name or intent["tool"],
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
