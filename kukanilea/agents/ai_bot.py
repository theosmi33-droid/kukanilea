from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class AiBot(BaseAgent):
    name = "WRK-AI_BOT"
    required_role = "USER"
    scope = "ai"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["llm_query", "ollama_status"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="AiBot handling request.")
