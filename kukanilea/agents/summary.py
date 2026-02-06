from __future__ import annotations

import json

from .base import AgentContext, AgentResult, BaseAgent
from kukanilea.guards import neutralize_untrusted_text


class SummaryAgent(BaseAgent):
    name = "summary"
    required_role = "ADMIN"
    scope = "summary"
    tools = ["summarize_doc"]

    def __init__(self, core_module, llm_provider=None) -> None:
        self.core = core_module
        self.llm = llm_provider

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "summary"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        token = context.token
        if not token:
            return AgentResult(text="Bitte gib einen Token an, den ich zusammenfassen soll.")
        payload = None
        if callable(getattr(self.core, "read_done", None)):
            payload = self.core.read_done(token)
        if payload is None and callable(getattr(self.core, "read_pending", None)):
            payload = self.core.read_pending(token)
        if not payload:
            return AgentResult(text="Dokument nicht gefunden.")
        text = str(payload.get("text") or payload.get("extracted_text") or "")
        if not text:
            text = json.dumps(payload, ensure_ascii=False)
        safe_text = neutralize_untrusted_text(text)
        if self.llm and getattr(self.llm, "available", False):
            summary = self.llm.summarize(safe_text)
        else:
            summary = safe_text.strip()[:400]
        return AgentResult(text=summary)
