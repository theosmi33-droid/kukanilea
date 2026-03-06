from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class LogBot(BaseAgent):
    name = "WRK-LOG_BOT"
    required_role = "USER"
    scope = "logging"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["view_logs", "analyze_logs"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="LogBot handling request.")
