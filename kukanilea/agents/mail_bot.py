from kukanilea.agents.base import AgentContext, AgentResult, BaseAgent

class MailBot(BaseAgent):
    name = "WRK-MAIL_BOT"
    required_role = "USER"
    scope = "mail"

    def can_handle(self, intent: str, message: str) -> bool:
        return intent in ["send_mail", "queue_check"]

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        self.log_heartbeat("RUNNING")
        return AgentResult(text="MailBot handling request.")
