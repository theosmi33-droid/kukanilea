from __future__ import annotations

from typing import Any

from .specialized import get_profile_prompt
from app.core.identity_parser import IdentityParser
from pathlib import Path

# Initialisierung des Parsers
IDENTITY_DIR = Path("instance/identity")
parser = IdentityParser(IDENTITY_DIR)

def build_prompt(user_msg: str, facts: list[dict[str, Any]], history: list[str] | None = None, role: str = "MASTER") -> str:
    # Lade dynamische Identität
    if role.upper() == "MASTER":
        profile_base = parser.get_master_instructions()
    else:
        profile_base = get_profile_prompt(role)
    
    system_prompt = (
        f"{profile_base}\n\n"
        "WICHTIG: Antworte als dieser Charakter. Nutze FACTS als Wissen. Nutze HISTORY als Gedächtnis bisheriger Schritte. "
        "WICHTIG: Wiederhole NIEMALS eine Aktion mit den exakt gleichen Parametern! "
        "Wenn du eine Information bereits erhalten hast oder die Aktion fehlschlug, "
        "nutze ein anderes Werkzeug oder antworte dem User direkt. "
        "Wenn du fertig bist, antworte normal als Text."
    )

    lines = [system_prompt, "", f"USER: {user_msg}", "", "FACTS:"]
    if not facts:
        lines.append("- (keine Fakten gefunden)")
    else:
        for fact in facts[:6]:
            lines.append(f"- {fact.get('text', '')}")
    
    if history:
        lines.append("")
        lines.append("HISTORY (Bisherige Schritte):")
        for h in history:
            lines.append(f"> {h}")

    lines.append("")
    lines.append("Antwort:")
    return "\n".join(lines)
