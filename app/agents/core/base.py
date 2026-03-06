from __future__ import annotations
import abc
from kukanilea.guards import ApprovalLevel, requires_approval

class BaseAgent(abc.ABC):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @abc.abstractmethod
    def execute(self, task: dict):
        pass

    def log_heartbeat(self, status: str, task_id: str = "IDLE"):
        print(f"[ID: {self.agent_id} | HEALTH: OK | TASK: {task_id}]")

    def validate_action(self, level: ApprovalLevel) -> bool:
        if requires_approval(level):
            print(f"[ID: {self.agent_id} | STATUS: CONFIRM_REQUIRED | LEVEL: {level.name}]")
            return False
        return True
