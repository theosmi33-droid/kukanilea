from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class NetBot(BaseAgent):
    name = "WRK-NET_BOT"
    required_role = "ADMIN"
    scope = "network"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["network_status", "cdn_check"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="NetBot handling request.")
