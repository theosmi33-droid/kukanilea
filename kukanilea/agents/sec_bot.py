from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class SecBot(BaseAgent):
    name = "WRK-SEC_BOT"
    required_role = "ADMIN"
    scope = "security"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["security_scan", "vulnerability_check"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="SecBot handling request.")
