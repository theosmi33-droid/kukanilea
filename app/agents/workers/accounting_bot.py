from app.agents.core.base import BaseAgent

class AccountingBot(BaseAgent):
    def __init__(self):
        super().__init__("WRK-ACCOUNTING_BOT")

    def execute(self, task: dict):
        self.log_heartbeat("RUNNING", task.get("id", "UNKNOWN"))
        return {"status": "ok", "agent": self.agent_id}
