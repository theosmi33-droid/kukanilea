from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class IndexAgent(BaseAgent):
    name = "index"
    required_role = "ADMIN"
    scope = "index"
    tools = ["index"]

    def __init__(self, core_module) -> None:
        self.core = core_module

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "index"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        if callable(getattr(self.core, "index_run_full", None)):
            result = self.core.index_run_full()
            return AgentResult(text=f"Indexierung abgeschlossen: {result}")
        return AgentResult(text="Indexierung ist nicht verfügbar.")
