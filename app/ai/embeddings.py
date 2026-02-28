from __future__ import annotations

import json
import os
import urllib.request
import logging
from typing import List, Optional

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
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            embedding = res_json.get("embedding")
            if isinstance(embedding, list):
                return [float(x) for x in embedding]
    except Exception as e:
        logger.error(f"Failed to generate embedding via Ollama: {e}")
        
    return None
