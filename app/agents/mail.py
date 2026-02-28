from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class MailAgent(BaseAgent):
    name = "mail"
    required_role = "OPERATOR"
    scope = "mail"
    tools = ["mail_generate"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "mail"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(
            text="Mail-Entwürfe findest du im Mail-Tab. Ich kann dort Vorlagen vorschlagen."
        )
