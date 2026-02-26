from __future__ import annotations

import os
from typing import Optional

import requests


import json
from pathlib import Path

def generate(prompt: str) -> Optional[str]:
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
        model = "qwen2.5:0.5b" # Safe default
        
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
