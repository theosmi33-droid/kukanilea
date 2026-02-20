from __future__ import annotations

import json
from typing import Any

import requests


def _api_base(base_url: str | None) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = str(api_key or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def openai_compat_is_available(
    *, base_url: str | None, api_key: str | None = None, timeout_s: int = 5
) -> bool:
    base = _api_base(base_url)
    if not base:
        return False
    try:
        response = requests.get(
            f"{base}/models",
            headers=_headers(api_key),
            timeout=max(1, int(timeout_s)),
        )
        return response.status_code == 200
    except requests.RequestException:
        return False


def openai_compat_chat(
    *,
    messages: list[dict[str, Any]],
    model: str,
    base_url: str,
    api_key: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    timeout_s: int = 90,
) -> dict[str, Any]:
    base = _api_base(base_url)
    if not base:
        raise RuntimeError("openai_compat_base_missing")
    model_name = str(model or "").strip()
    if not model_name:
        raise RuntimeError("openai_compat_model_missing")

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": list(messages or []),
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        response = requests.post(
            f"{base}/chat/completions",
            headers=_headers(api_key),
            json=payload,
            timeout=max(1, int(timeout_s)),
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("openai_compat_unreachable") from exc

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("openai_compat_invalid_json") from exc

    if not isinstance(data, dict):
        raise RuntimeError("openai_compat_invalid_response")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("openai_compat_missing_choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("openai_compat_invalid_choice")
    msg = first.get("message")
    if not isinstance(msg, dict):
        raise RuntimeError("openai_compat_missing_message")

    content = msg.get("content")
    text = content if isinstance(content, str) else ""
    tool_calls_raw = msg.get("tool_calls")
    tool_calls: list[dict[str, Any]] = []
    if isinstance(tool_calls_raw, list):
        for row in tool_calls_raw:
            if not isinstance(row, dict):
                continue
            function_raw = row.get("function")
            if not isinstance(function_raw, dict):
                continue
            fn_name = str(function_raw.get("name") or "").strip()
            fn_args = function_raw.get("arguments")
            if isinstance(fn_args, dict):
                fn_args = json.dumps(fn_args, ensure_ascii=False)
            if not isinstance(fn_args, str):
                fn_args = "{}"
            tool_calls.append(
                {
                    "id": str(row.get("id") or ""),
                    "type": str(row.get("type") or "function"),
                    "function": {"name": fn_name, "arguments": fn_args},
                }
            )

    return {"message": {"content": text, "tool_calls": tool_calls}}
