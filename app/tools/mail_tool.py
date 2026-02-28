from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.plugins.mail import MailAgent, MailInput, MailOptions

class MailGenerateTool(BaseTool):
    """
    Generates professional email drafts for craftsmen.
    """

    name = "mail_generate"
    description = "Erstellt einen professionellen E-Mail-Entwurf basierend auf Kontext und Fakten."
    input_schema = {
        "type": "object",
        "properties": {
            "context": {"type": "string", "description": "Der Grund für die E-Mail."},
            "facts": {"type": "object", "description": "Wichtige Fakten (z.B. Rechnungsnummer, Datum)."},
            "tone": {"type": "string", "enum": ["freundlich", "neutral", "bestimmt", "streng"], "default": "neutral"},
            "goal": {"type": "string", "enum": ["rabatt", "gutschrift", "ersatz", "nachbesserung", "ruecknahme"], "default": "gutschrift"}
        },
        "required": ["context"]
    }

    def run(self, context: str, facts: Optional[Dict[str, str]] = None, tone: str = "neutral", goal: str = "gutschrift") -> Any:
        agent = MailAgent()
        inp = MailInput(context=context, facts=facts or {}, attachments=[])
        opt = MailOptions(tone=tone, goal=goal, rewrite_mode="local")
        
        result = agent.generate(inp, opt)
        return {
            "status": "success",
            "subject": result["subject"],
            "body": result["body"],
            "checklist": result["checklist"]
        }

# Register tool
registry.register(MailGenerateTool())
