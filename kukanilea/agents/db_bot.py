from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class DbBot(BaseAgent):
    name = "WRK-DB_BOT"
    required_role = "ADMIN"
    scope = "database"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["db_migrate", "data_integrity"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="DbBot handling request.")
