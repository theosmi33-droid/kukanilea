from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class ReviewAgent(BaseAgent):
    name = "review"
    required_role = "OPERATOR"
    scope = "review"
    tools = ["review"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "review"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(
            text="Ich kann Vorschläge für die Ablage machen. Öffne einen Datensatz über die Trefferliste."
        )
