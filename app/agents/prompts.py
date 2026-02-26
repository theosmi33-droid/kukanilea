from __future__ import annotations

from typing import Any, Dict, List

SYSTEM_PROMPT = (
    "Du bist das KUKANILEA Enterprise OS – ein hochspezialisierter, lokaler KI-Operator für Handwerksbetriebe. "
    "Deine Maxime ist absolute Präzision und Datensouveränität. "
    "Nutze ausschließlich die bereitgestellten Fakten (FACTS). "
    "Interagiere mit dem System durch strukturierte Aktionen. "
    "Wenn eine Systemaktion (Task-Erstellung, Zeiterfassung, Suche) sinnvoll ist, antworte NUR mit JSON: "
    '{"action":"<tool_name>","args":{...}}. '
    "Andernfalls antworte präzise, sachlich und auf Deutsch. Verfalle niemals in Smalltalk."
)


def build_prompt(user_msg: str, facts: List[Dict[str, Any]]) -> str:
    lines = [SYSTEM_PROMPT, "", f"USER: {user_msg}", "", "FACTS:"]
    if not facts:
        lines.append("- (keine Fakten gefunden)")
    else:
        for fact in facts[:6]:
            lines.append(f"- {fact.get('text', '')}")
    lines.append("")
    lines.append("Antwort:")
    return "\n".join(lines)
