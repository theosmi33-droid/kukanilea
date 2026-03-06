from app.agents.core.base import BaseAgent

class Observer(BaseAgent):
    def __init__(self):
        super().__init__("SAFE-OBSERVER")

    def log_action(self, agent_id: str, action: str, status: str):
        print(f"[OBSERVER] Agent: {agent_id} | Action: {action} | Status: {status}")

    def execute(self, task: dict):
        # Observer is passive/reactive but can be invoked to audit a task
        pass
