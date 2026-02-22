"""
app/ai_chat/intent_parser.py
Read-Only Intent Parser für KUKANILEA Conversation Shortcuts.
"""

import re


def parse_user_intent(user_input: str) -> dict:
    """
    Parst den User-Input auf bekannte Muster (Shortcuts).
    Keine DB-Schreibvorgänge hier!
    """
    text = user_input.strip()

    # Muster: "Aufgabe: [Titel]"
    task_match = re.search(r"(?i)^Aufgabe:\s*(.+)$", text)
    if task_match:
        title = task_match.group(1).strip()
        return {
            "action": "create_task",
            "data": {
                "title": title,
                "status": "todo"
            }
        }

    # Fallback / Unbekannt
    return {
        "action": "unknown",
        "message": "Ich habe das nicht verstanden. Versuche es mit 'Aufgabe: [Titel]'"
    }
