"""
app/ai_chat/engine.py
Local-Only AI Engine for KUKANILEA using Ollama.
Offline-First & Read-Only by design.
"""

import json
import logging
from typing import Any

import httpx

# Constants
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 30.0
DEFAULT_MODEL = "llama3"  # or 'mistral' / 'phi3'

logger = logging.getLogger("kukanilea.ai_engine")

def ask_local_ai(prompt: str, tenant_id: str, context_data: dict[str, Any] | None = None) -> str:
    """
    Sends a prompt to the local Ollama instance.
    The assistant is strictly Read-Only and only for context analysis.
    """
    system_prompt = (
        "Du bist der KUKANILEA Handwerks-Assistent. Antworte kurz und präzise auf Deutsch. "
        "Du hast nur Lese- und Analyse-Zugriff auf die Daten des Mandanten (Tenant). "
        "Du darfst niemals behaupten, Änderungen an der Datenbank vornehmen zu können. "
        f"Aktueller Mandant (Tenant-ID): {tenant_id}. "
    )
    
    if context_data:
        context_json = json.dumps(context_data, ensure_ascii=False)
        system_prompt += f"\nZusätzlicher Kontext: {context_json}"

    payload = {
        "model": DEFAULT_MODEL,
        "prompt": f"{system_prompt}\n\nNutzer: {prompt}\n\nAssistent:",
        "stream": False
    }

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            response = client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", "Keine Antwort erhalten.")).strip()
            
    except httpx.ConnectError:
        logger.error("Ollama connection failed: Ensure 'ollama serve' is running.")
        return "Lokales KI-Modell aktuell nicht erreichbar. Bitte starte die Engine (Ollama)."
    except httpx.TimeoutException:
        logger.error("Ollama timeout: Model generation took too long.")
        return "Zeitüberschreitung bei der KI-Generierung. Das Modell antwortet zu langsam."
    except Exception as e:
        logger.error(f"Ollama unexpected error: {e}")
        return f"Fehler bei der KI-Abfrage: {str(e)}"
