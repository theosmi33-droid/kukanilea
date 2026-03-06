from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class FilesBot(BaseAgent):
    name = "WRK-FILES_BOT"
    required_role = "USER"
    scope = "files"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["file_op", "provenance_check"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="FilesBot handling request.")
