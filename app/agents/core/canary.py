from app.agents.core.base import BaseAgent

class Canary(BaseAgent):
    def __init__(self):
        super().__init__("SAFE-CANARY")

    def execute(self, task: dict):
        self.log_heartbeat("RUNNING", task.get("id", "UNKNOWN"))
        print(f"[{self.agent_id}] Running shadow task to detect regressions...")
        # TODO: Implement shadow execution logic
