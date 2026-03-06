from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List

class ApprovalLevel(IntEnum):
    LEVEL_1_READ_ONLY = 1
    LEVEL_2_VOLATILE = 2
    LEVEL_3_MODIFICATION = 3
    LEVEL_4_DESTRUCTIVE = 4

@dataclass
class AgentResult:
    text: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    error: str | None = None

@dataclass
class AgentContext:
    tenant_id: str
    user: str
    role: str
    kdnr: str = ""
    token: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

class BaseAgent:
    name = "base"
    required_role = "READONLY"
    scope = "general"
    tools: List[str] = []

    def can_handle(self, intent: str, message: str) -> bool:
        return False

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Nicht zuständig.")

    def log_heartbeat(self, status: str, task_id: str = "IDLE"):
        print(f"[ID: {self.name} | HEALTH: OK | TASK: {task_id}]")

    def validate_action(self, level: ApprovalLevel) -> bool:
        from kukanilea.guards import requires_approval
        if requires_approval(level):
            print(f"[ID: {self.name} | STATUS: CONFIRM_REQUIRED | LEVEL: {level.name}]")
            return False
        return True


class LLMAdapter:
    """Interface for future LLM providers."""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        raise NotImplementedError


class MockLLM(LLMAdapter):
    """Deterministic mock for tests/UI."""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        return f"[mocked] {prompt.strip()[:120]}"
