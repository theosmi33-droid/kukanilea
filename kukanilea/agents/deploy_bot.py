from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class DeployBot(BaseAgent):
    name = "WRK-DEPLOY_BOT"
    required_role = "ADMIN"
    scope = "deployment"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["build_release", "deploy_local"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="DeployBot handling request.")
