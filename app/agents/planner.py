"""
app/agents/planner.py
Agentischer Planer für KUKANILEA.
Zerlegt komplexe Nutzeranfragen in eine Sequenz von atomaren Schritten (Teilaufgaben).
"""

import json
import logging
from typing import List, Dict, Any
from app.ai.persona import persona_manager

logger = logging.getLogger("kukanilea.agents.planner")

class PlannerAgent:
    def __init__(self):
        self.role = "PLANNER"

    def create_plan(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Nutzt das LLM (hier simuliert/vorbereitet), um eine Aufgabenliste zu erstellen.
        In der Gold-Edition erfolgt hier ein LLM-Aufruf mit JSON-Mode.
        """
        logger.info(f"Erstelle Plan für: {user_input}")
        
        # Heuristik-Planer für den Prototyp (Phase 2.3)
        plan = []
        low = user_input.lower()
        
        if "angebot" in low or "rechnung" in low:
            plan.append({"step": 1, "task": "search_customer", "desc": "Kunde in der Datenbank identifizieren"})
            plan.append({"step": 2, "task": "get_prices", "desc": "Preise für Positionen ermitteln"})
            plan.append({"step": 3, "task": "generate_pdf", "desc": "Dokument generieren"})
            plan.append({"step": 4, "task": "send_mail_draft", "desc": "E-Mail Entwurf vorbereiten"})
        elif "termin" in low:
            plan.append({"step": 1, "task": "check_calendar", "desc": "Verfügbarkeit prüfen"})
            plan.append({"step": 2, "task": "create_appointment", "desc": "Termin eintragen"})
            plan.append({"step": 3, "task": "confirm_mail", "desc": "Bestätigung senden"})
        else:
            plan.append({"step": 1, "task": "general_answer", "desc": "Beantworte die Anfrage direkt"})
            
        return plan

planner = PlannerAgent()
