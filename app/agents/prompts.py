from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = (
    "Du bist ein lokaler KUKANILEA-Assistent. "
    "Nutze nur FACTS als Grundlage. "
    "Wenn eine Aktion erforderlich ist, antworte AUSSCHLIESSLICH mit JSON "
    '{"action":"<tool_name>","args":{...}}. '
    "Wenn keine Aktion notwendig ist, antworte kurz auf Deutsch."
)


def build_prompt(user_msg: str, facts: list[dict[str, Any]]) -> str:
    lines = [SYSTEM_PROMPT, "", f"USER: {user_msg}", "", "FACTS:"]
    if not facts:
        lines.append("- (keine Fakten gefunden)")
    else:
        for fact in facts[:6]:
            lines.append(f"- {fact.get('text', '')}")
    lines.append("")
    lines.append("Antwort:")
    return "\n".join(lines)
