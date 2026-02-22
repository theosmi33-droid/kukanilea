from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    text: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class AgentContext:
    tenant_id: str
    user: str
    role: str
    kdnr: str = ""
    token: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    name = "base"
    required_role = "READONLY"
    scope = "general"
    tools: list[str] = []

    def can_handle(self, intent: str, message: str) -> bool:
        return False

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        return AgentResult(text="Nicht zuständig.")


class LLMAdapter:
    """Interface for future LLM providers."""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        raise NotImplementedError


class MockLLM(LLMAdapter):
    """Deterministic mock for tests/UI."""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        return f"[mocked] {prompt.strip()[:120]}"
