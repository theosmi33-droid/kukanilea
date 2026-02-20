from __future__ import annotations

import json
from typing import Any

import requests

from app.ai.base import AIClient


class GeminiClient(AIClient):
    def __init__(
        self,
        *,
        base_url: str = "https://generativelanguage.googleapis.com",
        model: str = "gemini-1.5-flash",
        api_key: str = "",
        timeout_s: int = 60,
    ) -> None:
        self.base_url = str(
            base_url or "https://generativelanguage.googleapis.com"
        ).rstrip("/")
        self.default_model = str(model or "gemini-1.5-flash").strip()
        self.api_key = str(api_key or "").strip()
        self.timeout_s = max(1, int(timeout_s))

    @property
    def name(self) -> str:
        return "gemini"

    def _request(
        self,
        *,
        payload: dict[str, Any],
        model: str | None,
        timeout_s: int,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("gemini_api_key_missing")
        model_name = str(model or self.default_model).strip()
        url = f"{self.base_url}/v1beta/models/{model_name}:generateContent"
        resp = requests.post(
            url,
            params={"key": self.api_key},
            json=payload,
            timeout=max(1, min(int(timeout_s), self.timeout_s)),
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("gemini_invalid_response")
        return data

    def _to_contents(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        system_texts: list[str] = []
        contents: list[dict[str, Any]] = []
        for row in list(messages or []):
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "").strip().lower()
            content = row.get("content")
            text = content if isinstance(content, str) else ""
            if role == "system":
                if text.strip():
                    system_texts.append(text.strip())
                continue
            gemini_role = "model" if role == "assistant" else "user"
            if role == "tool":
                tool_name = str(row.get("name") or "tool").strip()
                text = f"Tool {tool_name}: {text}"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})
        if system_texts:
            return (
                {"parts": [{"text": "\n\n".join(system_texts)}]},
                contents,
            )
        return None, contents

    def _to_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        decls: list[dict[str, Any]] = []
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
            decls.append(
                {
                    "name": name,
                    "description": str(fn.get("description") or "").strip(),
                    "parameters": fn.get("parameters")
                    if isinstance(fn.get("parameters"), dict)
                    else {"type": "object", "properties": {}},
                }
            )
        if not decls:
            return []
        return [{"functionDeclarations": decls}]

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return {"message": {"content": "", "tool_calls": []}}
        first = candidates[0]
        if not isinstance(first, dict):
            return {"message": {"content": "", "tool_calls": []}}
        content = first.get("content")
        if not isinstance(content, dict):
            return {"message": {"content": "", "tool_calls": []}}
        parts = content.get("parts")
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, dict):
                    continue
                txt = part.get("text")
                if isinstance(txt, str) and txt:
                    text_parts.append(txt)
                fn = part.get("functionCall")
                if isinstance(fn, dict):
                    name = str(fn.get("name") or "").strip()
                    args_obj = fn.get("args")
                    if not isinstance(args_obj, dict):
                        args_obj = {}
                    tool_calls.append(
                        {
                            "id": name,
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
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": str(prompt)}]}]
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": str(system)}]}
        data = self._request(payload=payload, model=model, timeout_s=timeout_s)
        message = self._normalize(data).get("message")
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
            source = [{"role": "user", "content": str(prompt)}]
        else:
            source = list(messages)
        sys_instr, contents = self._to_contents(source)
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": str(system)}]}
        elif sys_instr is not None:
            payload["systemInstruction"] = sys_instr
        gemini_tools = self._to_tools(tools)
        if gemini_tools:
            payload["tools"] = gemini_tools
            payload["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
        data = self._request(payload=payload, model=model, timeout_s=timeout_s)
        return self._normalize(data)

    def health_check(self, timeout_s: int = 5) -> bool:
        if not self.api_key:
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/v1beta/models",
                params={"key": self.api_key},
                timeout=max(1, min(int(timeout_s), self.timeout_s)),
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
