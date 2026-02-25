from __future__ import annotations

import os
from typing import Optional

import requests


def generate(prompt: str) -> Optional[str]:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "phi3:instruct")
    url = f"{host}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response")
        if not isinstance(text, str):
            return None
        return text.strip()
    except Exception:
        return None
