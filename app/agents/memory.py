from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class MemoryAgent(BaseAgent):
    name = "memory"
    required_role = "OPERATOR"
    scope = "memory"
    tools = ["memory_store", "memory_search"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "memory"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Mein semantisches Gedächtnis ist aktiv und lernt mit.")
