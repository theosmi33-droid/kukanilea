from __future__ import annotations

import json
import os
from typing import Any

import requests

from .errors import OllamaBadResponse, OllamaUnavailable

DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
DEFAULT_OLLAMA_TIMEOUT_S = int(os.environ.get("OLLAMA_TIMEOUT", "300"))


def _base(base_url: str | None = None) -> str:
    return str(base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def ollama_is_available(base_url: str | None = None, timeout_s: int = 5) -> bool:
    try:
        response = requests.get(f"{_base(base_url)}/api/tags", timeout=timeout_s)
        return response.status_code == 200
    except requests.RequestException:
        return False


def ollama_list_models(base_url: str | None = None, timeout_s: int = 5) -> list[str]:
    try:
        response = requests.get(f"{_base(base_url)}/api/tags", timeout=timeout_s)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise OllamaUnavailable("ollama_unreachable") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise OllamaBadResponse("invalid_json") from exc

    models = payload.get("models")
    if not isinstance(models, list):
        return []
    out: list[str] = []
    for row in models:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def ollama_chat(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    fmt: dict[str, Any] | str | None = None,
    base_url: str | None = None,
    timeout_s: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": str(model or DEFAULT_OLLAMA_MODEL),
        "messages": list(messages or []),
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    if fmt is not None:
        payload["format"] = fmt

    url = f"{_base(base_url)}/api/chat"
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=int(timeout_s or DEFAULT_OLLAMA_TIMEOUT_S),
        )
    except requests.RequestException as exc:
        raise OllamaUnavailable("ollama_chat_unreachable") from exc

    if int(getattr(response, "status_code", 0)) >= 400:
        error_text = ""
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict):
                error_text = str(error_payload.get("error") or "").strip()
        except Exception:
            error_text = str(getattr(response, "text", "") or "").strip()
        normalized = error_text.lower()
        if "model" in normalized and "not found" in normalized:
            raise OllamaBadResponse("ollama_model_not_found")
        raise OllamaBadResponse(f"ollama_http_{int(response.status_code)}")

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise OllamaBadResponse("ollama_response_not_json") from exc

    if not isinstance(data, dict):
        raise OllamaBadResponse("ollama_response_invalid")
    if not isinstance(data.get("message"), dict):
        raise OllamaBadResponse("ollama_missing_message")
    return data
