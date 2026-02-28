"""
app/ai/model_manager.py
Local AI model management for KUKANILEA v2.1.
Supports Ollama models, switching, and auto-detection.
"""

import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("kukanilea.ai.manager")

OLLAMA_BASE = "http://localhost:11434"

def get_installed_models() -> List[str]:
    """Step 42: Detect available models automatically."""
    try:
        res = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        if res.status_code == 200:
            models = res.json().get("models", [])
            return [m["name"] for m in models]
    except Exception as e:
        logger.warning(f"Ollama detection failed: {e}")
        
    return []

def detect_gpu() -> Dict[str, Any]:
    """Step 45: Detect GPU availability (Mock for now)."""
    # Real implementation would use nvidia-smi or direct APIs
    return {"gpu_available": False, "device": "CPU"}

def switch_model(model_name: str) -> bool:
    """Step 44: Allow model switching."""
    installed = get_installed_models()
    if model_name in installed:
        logger.info(f"Switching to AI model: {model_name}")
        # Save to config/tenant settings in future
        return True
        
    logger.error(f"Model {model_name} not found.")
    return False

def pull_model(model_name: str):
    """Integrates with Ollama API for model fetching."""
    try:
        requests.post(f"{OLLAMA_BASE}/api/pull", json={"name": model_name, "stream": False}, timeout=1)
    except Exception:
        pass
