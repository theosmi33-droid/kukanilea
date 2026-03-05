from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-/]{6,}\d)")
COMPANY_RE = re.compile(r"\b(?:firma|company|kunde|kundin)\s*[:\-]?\s*([A-Za-z0-9äöüÄÖÜß\s&.-]{2,80})", re.IGNORECASE)
NAME_RE = re.compile(r"\b(?:ich\s+bin|mein\s+name\s+ist|name\s*[:\-])\s*([A-Za-zäöüÄÖÜß\-\s]{2,80})", re.IGNORECASE)


WRITE_ACTION_TYPES = {"create_task", "create_appointment", "mail_generate", "messenger_send", "mail_send"}
WRITE_PREFIXES = ("create_", "delete_", "update_", "send_", "mail_", "messenger_")



def _pick_match(pattern: re.Pattern[str], message: str) -> str:
    match = pattern.search(message)
    if not match:
        return ""
    groups = match.groups()
    return str((groups[0] if groups else match.group(0)) or "").strip(" .,:;\n\t")



def _is_write_action(action_type: str) -> bool:
    return action_type in WRITE_ACTION_TYPES or action_type.startswith(WRITE_PREFIXES)



def parse_chat_intake(message: str, actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    text = str(message or "").strip()
    lowered = text.lower()

    email = _pick_match(EMAIL_RE, text)
    phone = _pick_match(PHONE_RE, text)
    company = _pick_match(COMPANY_RE, text)
    contact_name = _pick_match(NAME_RE, text)

    lead_fields = {
        "contact_name": contact_name or None,
        "contact_email": email or None,
        "contact_phone": phone or None,
        "company": company or None,
        "source": "chat",
        "intent": "action_request" if any(k in lowered for k in ("sende", "schick", "erstelle", "create", "update")) else "information",
    }

    suggested_next_actions: list[dict[str, Any]] = []
    for action in actions or []:
        action_type = str(action.get("type") or "")
        if not action_type:
            continue
        suggested_next_actions.append(
            {
                "type": action_type,
                "confirm_required": _is_write_action(action_type),
                "reason": "write_operation" if _is_write_action(action_type) else "read_or_assistive",
            }
        )

    if not suggested_next_actions:
        if any(k in lowered for k in ("task", "aufgabe", "todo")):
            suggested_next_actions.append({"type": "create_task", "confirm_required": True, "reason": "chat_intent_task"})
        if any(k in lowered for k in ("termin", "kalender", "meeting")):
            suggested_next_actions.append({"type": "create_appointment", "confirm_required": True, "reason": "chat_intent_calendar"})
        if any(k in lowered for k in ("mail", "email", "nachricht", "sende", "schick")):
            suggested_next_actions.append({"type": "messenger_send", "confirm_required": True, "reason": "chat_intent_message"})

    return {
        "lead_fields": lead_fields,
        "suggested_next_actions": suggested_next_actions,
        "message_preview": text[:180],
    }
