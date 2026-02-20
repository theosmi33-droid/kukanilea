from __future__ import annotations

import json
from typing import Any

import requests

from app.ai.base import AIClient


class AnthropicClient(AIClient):
    def __init__(
        self,
        *,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-3-5-sonnet-latest",
        api_key: str = "",
        timeout_s: int = 60,
        anthropic_version: str = "2023-06-01",
        max_tokens: int = 1024,
    ) -> None:
        self.base_url = str(base_url or "https://api.anthropic.com").rstrip("/")
        self.default_model = str(model or "").strip()
        self.api_key = str(api_key or "").strip()
        self.timeout_s = max(1, int(timeout_s))
        self.anthropic_version = str(anthropic_version or "2023-06-01").strip()
        self.max_tokens = max(1, int(max_tokens))

    @property
    def name(self) -> str:
        return "anthropic"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.anthropic_version,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _to_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        out: list[dict[str, Any]] = []
        for row in list(messages or []):
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "").strip().lower()
            if role == "system":
                content = row.get("content")
                if isinstance(content, str) and content.strip():
                    system_parts.append(content.strip())
                continue
            if role == "assistant":
                target_role = "assistant"
            else:
                target_role = "user"

            content = row.get("content")
            text = content if isinstance(content, str) else ""
            if role == "tool":
                tool_name = str(row.get("name") or "tool").strip()
                text = f"Tool {tool_name}: {text}"
            out.append({"role": target_role, "content": text})
        system = "\n\n".join(system_parts).strip() if system_parts else None
        return system, out

    def _to_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in list(tools or []):
            if not isinstance(row, dict):
                continue
            if str(row.get("type") or "").strip().lower() != "function":
                continue
            fn = row.get("function")
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name") or "").strip()
            if not name:
                continue
            out.append(
                {
                    "name": name,
                    "description": str(fn.get("description") or "").strip(),
                    "input_schema": fn.get("parameters")
                    if isinstance(fn.get("parameters"), dict)
                    else {"type": "object", "properties": {}},
                }
            )
        return out

    def _request_messages(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": str(model or self.default_model),
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = {"type": "auto"}
        resp = requests.post(
            f"{self.base_url}/v1/messages",
            headers=self._headers(),
            json=payload,
            timeout=max(1, min(int(timeout_s), self.timeout_s)),
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("anthropic_invalid_response")
        return data

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        content_blocks = payload.get("content")
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                btype = str(block.get("type") or "").strip().lower()
                if btype == "text":
                    txt = block.get("text")
                    if isinstance(txt, str) and txt:
                        text_parts.append(txt)
                if btype == "tool_use":
                    name = str(block.get("name") or "").strip()
                    args_obj = block.get("input")
                    if not isinstance(args_obj, dict):
                        args_obj = {}
                    tool_calls.append(
                        {
                            "id": str(block.get("id") or ""),
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args_obj, ensure_ascii=False),
                            },
                        }
                    )
        return {
            "message": {
                "content": "\n".join(text_parts).strip(),
                "tool_calls": tool_calls,
            }
        }

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        **kwargs: Any,
    ) -> str:
        payload = self._request_messages(
            messages=[{"role": "user", "content": str(prompt)}],
            system=system,
            model=model,
            timeout_s=timeout_s,
            tools=None,
        )
        normalized = self._normalize(payload)
        message = normalized.get("message")
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
        if messages is None:
            source_messages: list[dict[str, Any]] = [
                {"role": "user", "content": str(prompt)}
            ]
        else:
            source_messages = list(messages)
        system_msg, anthropic_messages = self._to_messages(source_messages)
        payload = self._request_messages(
            messages=anthropic_messages,
            system=system or system_msg,
            model=model,
            timeout_s=timeout_s,
            tools=self._to_tools(tools),
        )
        return self._normalize(payload)

    def health_check(self, timeout_s: int = 5) -> bool:
        if not self.api_key:
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/v1/models",
                headers=self._headers(),
                timeout=max(1, min(int(timeout_s), self.timeout_s)),
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
