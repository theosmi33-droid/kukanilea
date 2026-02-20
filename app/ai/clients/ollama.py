from __future__ import annotations

from typing import Any

from app.ai.base import AIClient
from app.ai.ollama_client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_S,
    ollama_chat,
    ollama_is_available,
)


class OllamaProviderClient(AIClient):
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout_s: int = DEFAULT_OLLAMA_TIMEOUT_S,
    ) -> None:
        self.base_url = str(base_url or DEFAULT_OLLAMA_BASE_URL).strip()
        self.default_model = str(model or DEFAULT_OLLAMA_MODEL).strip()
        self.timeout_s = max(1, int(timeout_s or DEFAULT_OLLAMA_TIMEOUT_S))

    @property
    def name(self) -> str:
        return "ollama"

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        **kwargs: Any,
    ) -> str:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": str(system)})
        messages.append({"role": "user", "content": str(prompt)})
        payload = ollama_chat(
            messages=messages,
            model=str(model or self.default_model),
            base_url=self.base_url,
            timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
        )
        message = payload.get("message") if isinstance(payload, dict) else None
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        return content if isinstance(content, str) else ""

    def generate_text_with_tools(
        self,
        *,
        prompt: str,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if messages is not None:
            payload_messages = list(messages)
        else:
            payload_messages = []
            if system:
                payload_messages.append({"role": "system", "content": str(system)})
            payload_messages.append({"role": "user", "content": str(prompt)})
        return ollama_chat(
            messages=payload_messages,
            model=str(model or self.default_model),
            base_url=self.base_url,
            tools=list(tools or []),
            timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
        )

    def health_check(self, timeout_s: int = 5) -> bool:
        return bool(
            ollama_is_available(
                base_url=self.base_url,
                timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
            )
        )
