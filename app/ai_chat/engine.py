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
OLLAMA_TIMEOUT = 60.0
DEFAULT_MODEL = "llama3.1:8b" 

logger = logging.getLogger("kukanilea.ai_engine")

def ask_local_ai(prompt: str, tenant_id: str, context_data: dict[str, Any] | None = None) -> str:
    """
    Sends a prompt to the local Ollama instance.
    Persona: Professional, helpful 'Digital Handwerksmeister'.
    """
    system_prompt = (
        "Du bist KUKANILEA, der digitale Handwerksmeister. Dein Ton ist professionell, "
        "direkt und hilfsbereit – so wie man es unter Kollegen auf der Baustelle oder im Büro schätzt. "
        "Du sprichst den Nutzer immer mit 'Du' an (kollegialer Ton unter Handwerkern). "
        "Du hilfst bei der Analyse von Betriebsdaten, Kundenanfragen und Projekten. "
        "Deine Antworten sind präzise, auf Deutsch und ohne unnötiges KI-Geschwafel. "
        "Wichtig: Du arbeitest lokal und sicher. Du hast Lese-Zugriff auf die Daten. "
        f"Aktueller Betrieb (Tenant): {tenant_id}. "
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
