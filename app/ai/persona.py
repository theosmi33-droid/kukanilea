"""
app/ai/persona.py
Lädt und verwaltet die 'DNA' der KI aus der SOUL.md.
Definiert Tonalität, Verhaltensregeln und Wissensgrenzen.
"""

import os
from pathlib import Path
import logging

logger = logging.getLogger("kukanilea.ai.persona")

class PersonaManager:
    def __init__(self, soul_path: Path = None):
        if soul_path is None:
            # Fallback Pfad
            self.soul_path = Path(__file__).parent / "SOUL.md"
        else:
            self.soul_path = soul_path
            
        self.identity_context = ""
        self.load_soul()

    def load_soul(self):
        """Liest die SOUL.md ein und bereitet sie als System-Prompt auf."""
        try:
            if self.soul_path.exists():
                content = self.soul_path.read_text(encoding="utf-8")
                # Wir bereiten den Text so vor, dass er als permanenter Kontext dient
                self.identity_context = f"""--- KI-IDENTITÄT (SOUL.md) ---
{content}
--- ENDE IDENTITÄT ---
"""
                logger.info("KI-Persona (SOUL.md) erfolgreich geladen.")
            else:
                self.identity_context = "Du bist der digitale Werkstattmeister von KUKANILEA. Antworte formell und präzise auf Deutsch."
                logger.warning(f"SOUL.md nicht gefunden unter {self.soul_path}. Nutze Standard-Persona.")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Persona: {e}")
            self.identity_context = "Du bist ein KI-Assistent."

    def get_system_prompt(self) -> str:
        """Gibt den kombinierten System-Prompt zurück."""
        return f"""{self.identity_context}

Zusätzliche Anweisung: Wenn der Nutzer nach Informationen fragt, die du nicht lokal hast, 
nutze das Tool 'web_search' (falls verfügbar), um Fakten zu prüfen."""

# Singleton für globale Nutzung
persona_manager = PersonaManager()
