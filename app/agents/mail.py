from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class MailAgent(BaseAgent):
    name = "mail"
    required_role = "OPERATOR"
    scope = "mail"
    tools = ["mail_generate", "mail_send"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "mail"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        text = message.lower()
        if "send" in text or "schick" in text:
            return AgentResult(
                text="Ich habe einen Mail-Versand vorbereitet. Bitte bestätige die Aktion im Mail-Hub.",
                actions=[{
                    "type": "mail_send",
                    "confirm_required": True,
                    "target": "customer",
                    "reason": "user_request"
                }]
            )
        return AgentResult(
            text="Mail-Entwürfe findest du im Mail-Tab. Ich kann dort Vorlagen vorschlagen."
        )
