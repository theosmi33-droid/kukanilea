from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class ArchiveAgent(BaseAgent):
    name = "archive"
    required_role = "STAFF"
    scope = "archive"
    tools = ["archive"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "archive"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Archivierung ist in der Review-Ansicht verfügbar.")
