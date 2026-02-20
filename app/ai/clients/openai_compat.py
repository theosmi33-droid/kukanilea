from __future__ import annotations

from typing import Any

from app.ai.base import AIClient
from app.ai.openai_compat_client import openai_compat_chat, openai_compat_is_available


class OpenAICompatClient(AIClient):
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: int = 60,
    ) -> None:
        self._provider_name = str(provider_name or "openai_compat").strip().lower()
        self.base_url = str(base_url or "").strip()
        self.default_model = str(model or "").strip()
        self.api_key = str(api_key or "").strip()
        self.timeout_s = max(1, int(timeout_s))

    @property
    def name(self) -> str:
        return self._provider_name

    def _resolve_model(self, model: str | None) -> str:
        return str(model or self.default_model or "").strip()

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
        response = openai_compat_chat(
            messages=messages,
            model=self._resolve_model(model),
            base_url=self.base_url,
            api_key=self.api_key,
            timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
        )
        message = response.get("message") if isinstance(response, dict) else None
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

        return openai_compat_chat(
            messages=payload_messages,
            model=self._resolve_model(model),
            base_url=self.base_url,
            api_key=self.api_key,
            tools=list(tools or []),
            timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
        )

    def health_check(self, timeout_s: int = 5) -> bool:
        return openai_compat_is_available(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
        )
