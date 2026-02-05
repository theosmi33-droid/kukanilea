from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class SummaryAgent(BaseAgent):
    name = "summary"
    required_role = "ADMIN"
    scope = "summary"
    tools = ["summary"]

    def __init__(self, core_module) -> None:
        self.core = core_module

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "summary"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Zusammenfassung ist in dieser Version heuristisch nicht verfügbar.")
