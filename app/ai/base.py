from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIClient(ABC):
    """Provider-agnostic contract for local/cloud LLM backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier (e.g. 'vllm', 'ollama')."""

    @abstractmethod
    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        **kwargs: Any,
    ) -> str:
        """Generate plain text response."""

    @abstractmethod
    def generate_text_with_tools(
        self,
        *,
        prompt: str,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate response including optional tool calls.

        Normalized return format:
        {
          "message": {
            "content": "<text>",
            "tool_calls": [ ... ]
          }
        }
        """

    @abstractmethod
    def health_check(self, timeout_s: int = 5) -> bool:
        """Lightweight availability probe."""
