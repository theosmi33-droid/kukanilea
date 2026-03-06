from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class SyncBot(BaseAgent):
    name = "WRK-SYNC_BOT"
    required_role = "USER"
    scope = "synchronization"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["sync_data", "p2p_status"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="SyncBot handling request.")
