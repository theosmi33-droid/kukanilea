from __future__ import annotations

import re

from .base import AgentContext, AgentResult, BaseAgent


class OpenFileAgent(BaseAgent):
    name = "open_file"
    required_role = "READONLY"
    scope = "ui"
    tools = ["open_doc"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "open_token"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        token = context.token
        if not token:
            match = re.search(r"(token|doc|id)\s*[:#]?\s*([a-f0-9]{16,64})", message, re.IGNORECASE)
            if match:
                token = match.group(2)
        if not token:
            return AgentResult(text="Bitte gib mir einen Token/ID, den ich öffnen soll.")
        return AgentResult(text=f"Öffne {token}…", actions=[{"type": "open_token", "token": token}])
