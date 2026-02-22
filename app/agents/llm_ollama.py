from __future__ import annotations

import os
from typing import Any

import requests


def _host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def _model() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def _timeout_s() -> int:
    try:
        return int(os.environ.get("OLLAMA_TIMEOUT", "300"))
    except Exception:
        return 300


def is_available() -> bool:
    try:
        resp = requests.get(f"{_host()}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        resp = requests.get(f"{_host()}/api/tags", timeout=5)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return []
    rows = payload.get("models")
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {
        "model": str(model or _model()),
        "messages": list(messages or []),
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    try:
        resp = requests.post(f"{_host()}/api/chat", json=payload, timeout=_timeout_s())
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def generate(prompt: str) -> str | None:
    url = f"{_host()}/api/generate"
    payload = {"model": _model(), "prompt": prompt, "stream": False}
    try:
        resp = requests.post(url, json=payload, timeout=_timeout_s())
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response")
        if not isinstance(text, str):
            return None
        return text.strip()
    except Exception:
        return None
