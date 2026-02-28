from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class UploadAgent(BaseAgent):
    name = "upload"
    required_role = "OPERATOR"
    scope = "upload"
    tools = ["upload"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "upload"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Upload-Aufträge bitte über die Upload-Seite starten.")
