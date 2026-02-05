from __future__ import annotations

import re

from .base import AgentContext, AgentResult, BaseAgent


class CustomerAgent(BaseAgent):
    name = "customer"
    required_role = "OPERATOR"
    scope = "customer"
    tools = ["show_customer"]

    def __init__(self, core_module) -> None:
        self.core = core_module

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "customer_lookup"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        kdnr = context.kdnr
        match = re.search(r"kdnr\s*(\d{3,})", message, re.IGNORECASE)
        if match:
            kdnr = match.group(1)
        if not kdnr:
            return AgentResult(text="Bitte gib eine KDNR an.")
        if callable(getattr(self.core, "assistant_search", None)):
            results = self.core.assistant_search(query=kdnr, kdnr=kdnr, limit=5, role=context.role, tenant_id=context.tenant_id)
            if results:
                first = results[0]
                return AgentResult(
                    text=f"Kunde {first.get('kdnr','')} – letzter Treffer: {first.get('file_name','')} ({first.get('doc_date','')})",
                    data={"results": results},
                )
        return AgentResult(text="Kein Kunde gefunden.")
