from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class MeshAgent(BaseAgent):
    name = "mesh"
    required_role = "ADMIN"
    scope = "network"
    tools = ["mesh_sync"]

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "mesh"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Mesh-Netzwerk Synchronisation kann über die Admin-Tools gestartet werden.")
