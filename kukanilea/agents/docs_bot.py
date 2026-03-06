from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class DocsBot(BaseAgent):
    name = "WRK-DOCS_BOT"
    required_role = "USER"
    scope = "documentation"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["update_docs", "adr_maintain"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="DocsBot handling request.")
