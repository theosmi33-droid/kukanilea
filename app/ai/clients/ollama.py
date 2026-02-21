from __future__ import annotations

import os
from typing import Any

from app.ai.base import AIClient
from app.ai.errors import OllamaBadResponse, OllamaUnavailable
from app.ai.ollama_client import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_S,
    ollama_chat,
    ollama_is_available,
)


def _parse_model_list(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = [str(row) for row in value]
    out: list[str] = []
    for part in parts:
        model = str(part or "").strip()
        if model and model not in out:
            out.append(model)
    return out


class OllamaProviderClient(AIClient):
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout_s: int = DEFAULT_OLLAMA_TIMEOUT_S,
        fallback_models: str | list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.base_url = str(base_url or DEFAULT_OLLAMA_BASE_URL).strip()
        configured_default = str(model or DEFAULT_OLLAMA_MODEL).strip()
        env_fallback = os.environ.get(
            "KUKANILEA_OLLAMA_MODEL_FALLBACKS", "llama3.2:3b,qwen2.5:3b"
        )
        fallback_source = (
            fallback_models if fallback_models is not None else env_fallback
        )
        configured_models = [configured_default, *_parse_model_list(fallback_source)]
        seen: set[str] = set()
        self.model_candidates: list[str] = []
        for model_name in configured_models:
            if not model_name or model_name in seen:
                continue
            seen.add(model_name)
            self.model_candidates.append(model_name)
        if not self.model_candidates:
            self.model_candidates = [DEFAULT_OLLAMA_MODEL]
        self.default_model = self.model_candidates[0]
        self.timeout_s = max(1, int(timeout_s or DEFAULT_OLLAMA_TIMEOUT_S))

    @property
    def name(self) -> str:
        return "ollama"

    def _candidate_models(self, requested_model: str | None) -> list[str]:
        requested = str(requested_model or "").strip()
        if not requested:
            return list(self.model_candidates)
        return [requested, *[m for m in self.model_candidates if m != requested]]

    def _chat_with_fallback(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        timeout_s: int = 90,
    ) -> dict[str, Any]:
        timeout = max(1, min(int(timeout_s), self.timeout_s))
        last_error: Exception | None = None
        for candidate_model in self._candidate_models(model):
            try:
                return ollama_chat(
                    messages=messages,
                    model=candidate_model,
                    base_url=self.base_url,
                    tools=tools,
                    timeout_s=timeout,
                )
            except OllamaUnavailable:
                # Connectivity/service outage: fail fast and let provider router pick fallback provider.
                raise
            except OllamaBadResponse as exc:
                # Model-specific or transient bad responses: try next configured local model.
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise OllamaBadResponse("ollama_no_model_candidates")

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
        payload = self._chat_with_fallback(
            messages=messages,
            model=model,
            timeout_s=timeout_s,
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
        return self._chat_with_fallback(
            messages=payload_messages,
            tools=list(tools or []),
            model=model,
            timeout_s=timeout_s,
        )

    def health_check(self, timeout_s: int = 5) -> bool:
        return bool(
            ollama_is_available(
                base_url=self.base_url,
                timeout_s=max(1, min(int(timeout_s), self.timeout_s)),
            )
        )
