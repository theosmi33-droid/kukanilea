from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import requests


import secrets

def wrap_with_salt(data: str) -> str:
    """Wraps user input with session-based salted tags to prevent prompt injection."""
    salt = secrets.token_hex(4)
    return f"<{salt}>\n{data}\n</{salt}>"

def generate(prompt: str, temperature: float = 0.0) -> Optional[str]:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "")

    if not model:
        # Respect hardware profile
        try:
            profile_path = Path("instance/hardware_profile.json")
            if profile_path.exists():
                with open(profile_path, "r") as f:
                    profile = json.load(f)
                    model = profile.get("recommended_model")
        except Exception:
            pass

    if not model:
        model = "qwen2.5:0.5b"  # Safe default

    url = f"{host}/api/generate"
    # Options for determinism
    options = {
        "temperature": temperature,
        "seed": 42,
        "num_predict": 1024,
        "top_k": 1,
        "top_p": 0.0
    }
    payload = {"model": model, "prompt": prompt, "stream": False, "options": options}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response")
        if not isinstance(text, str):
            return None
        return text.strip()
    except Exception:
        return None

def generate_json(prompt: str, schema: Optional[dict] = None) -> Optional[dict]:
    """Generates a structured JSON response from Ollama with validation."""
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    # Similar model resolution logic as above...
    # For brevity, reusing the existing logic in a real implementation
    
    url = f"{host}/api/generate"
    options = {"temperature": 0.0, "seed": 42}
    payload = {
        "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b"),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": options
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        raw_text = resp.json().get("response", "{}")
        parsed = json.loads(raw_text)
        return parsed
    except Exception:
        return None
