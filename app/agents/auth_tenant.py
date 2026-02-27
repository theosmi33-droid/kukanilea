from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class AuthTenantAgent(BaseAgent):
    name = "auth_tenant"
    required_role = "READONLY"
    scope = "tenant"
    tools = ["tenant"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "tenant"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text=f"Aktiver Mandant: {context.tenant_id}")
