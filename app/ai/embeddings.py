from __future__ import annotations

import logging
import os
from typing import List, Optional

import requests

logger = logging.getLogger("kukanilea.ai.embeddings")

def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generates a semantic embedding for the given text using local Ollama.
    Uses 'nomic-embed-text' as a high-performance local default.
    """
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    url = f"{host}/api/embeddings"
    payload = {
        "model": model,
        "prompt": text
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            timeout=10.0,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        res_json = resp.json()
        if isinstance(res_json, dict):
            embedding = res_json.get("embedding")
            if isinstance(embedding, list):
                return [float(x) for x in embedding]
    except Exception as e:
        logger.error(f"Failed to generate embedding via Ollama: {e}")

    return None
