"""
app/ai_chat/intent_parser.py
Read-Only Intent Parser für KUKANILEA Conversation Shortcuts.
"""

import re


def parse_user_intent(user_input: str) -> dict:
    """
    Parst den User-Input auf bekannte Handlungen (Agentic Actions).
    """
    text = user_input.strip()

    # CRM: "Leg einen neuen Kunden [Name] an"
    crm_match = re.search(r"(?i)(?:neuen\s+)?Kunden\s+(?:anlegen|erstellen|registrieren):\s*(.+)$", text)
    if not crm_match:
        crm_match = re.search(r"(?i)Leg\s+(?:einen\s+)?neuen\s+Kunden\s+an\s+(?:für\s+)?(.+)$", text)
    
    if crm_match:
        name = crm_match.group(1).strip()
        return {
            "action": "create_customer",
            "data": {"name": name}
        }

    # Tasks: "Notiere Aufgabe: [Titel]" oder "Leg Projekt an: [Titel]"
    task_match = re.search(r"(?i)(?:Aufgabe|Projekt):\s*(.+)$", text)
    if not task_match:
        task_match = re.search(r"(?i)(?:Notiere|Erstelle)\s+(?:eine\s+)?(?:Aufgabe|Projekt)\s+(?:für\s+)?(.+)$", text)
        
    if task_match:
        title = task_match.group(1).strip()
        return {
            "action": "create_task",
            "data": {"title": title, "status": "todo"}
        }

    # Fallback / Unbekannt
    return {
        "action": "chat",
        "data": {}
    }
