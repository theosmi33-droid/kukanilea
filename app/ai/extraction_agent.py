"""
app/ai/extraction_agent.py
Spezialisierter Agent zur Extraktion von Belegdaten (Rechnungen, Angebote) 
aus unstrukturiertem OCR-Text mittels lokalem LLM (Ollama).
"""

import logging
import json
import os
import re
from typing import Any, Optional, Dict
from .ollama_client import ollama_chat

logger = logging.getLogger("kukanilea.ai.extraction")

# Pfad zu den Templates
TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "extractors", "receipt_templates.json")

EXTRACTION_PROMPT = """
Du bist ein Experte für die Analyse von Handwerksrechnungen und Belegen.
Deine Aufgabe ist es, aus dem folgenden OCR-Text die wichtigsten Daten zu extrahieren.
Gib das Ergebnis ausschließlich als valides JSON zurück.

Zu extrahierende Felder:
- doctype: (RECHNUNG, ANGEBOT, AUFTRAGSBESTAETIGUNG, MAHNUNG, SONSTIGES)
- doc_date: Datum im Format YYYY-MM-DD
- kdnr: Kundennummer (falls vorhanden)
- invoice_no: Rechnungsnummer (falls vorhanden)
- net_amount: Nettobetrag (Zahlwert)
- vat_amount: MwSt-Betrag (Zahlwert)
- total_amount: Gesamtbetrag (Brutto, Zahlwert)
- currency: Währung (EUR, USD, etc.)
- vendor_name: Name des Ausstellers (Firma)

OCR-TEXT:
{text}

JSON-Antwort:
"""

class ExtractionAgent:
    def __init__(self, model: str = "llama3.2:1b"):
        self.model = model
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Any]:
        try:
            if os.path.exists(TEMPLATES_PATH):
                with open(TEMPLATES_PATH, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Fehler beim Laden der OCR-Templates: {e}")
        return {"vendors": []}

    def _fuzzy_match_vendor(self, extracted_name: str, ocr_text: str) -> str:
        """Prüft, ob der extrahierte Name oder der OCR-Text bekannte Lieferanten enthält."""
        text_to_search = f"{extracted_name} {ocr_text[:1000]}".lower()
        for vendor in self.templates.get("vendors", []):
            for kw in vendor.get("keywords", []):
                if kw.lower() in text_to_search:
                    return vendor["name"]
        return extracted_name

    def validate_vat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prüft die mathematische Korrektheit der MwSt (Netto + MwSt == Brutto)."""
        try:
            net = float(data.get("net_amount") or 0)
            vat = float(data.get("vat_amount") or 0)
            total = float(data.get("total_amount") or 0)

            if total > 0 and abs((net + vat) - total) < 0.05:
                data["vat_valid"] = True
            elif total > 0:
                # Versuch, aus Brutto und Standard-Sätzen zu rechnen, falls Netto fehlt
                data["vat_valid"] = False
                logger.warning(f"MwSt Validierung fehlgeschlagen: {net} + {vat} != {total}")
        except (ValueError, TypeError):
            data["vat_valid"] = False
        return data

    def refine_extraction(self, ocr_text: str) -> dict[str, Any]:
        """Nutzt LLM zur strukturierten Extraktion aus OCR-Text."""
        if not ocr_text or len(ocr_text.strip()) < 10:
            return {}

        messages = [
            {"role": "system", "content": "Du bist ein präziser Daten-Extraktor für Handwerksbelege. Antworte nur mit JSON."},
            {"role": "user", "content": EXTRACTION_PROMPT.format(text=ocr_text[:4000])}
        ]

        try:
            # Wir fordern JSON-Format vom Ollama-Server an
            response = ollama_chat(
                messages=messages,
                model=self.model,
                fmt="json"
            )
            
            content = response.get("message", {}).get("content", "{}")
            data = json.loads(content)
            
            # Phase 6: Auto-Learning Refinement (Gelerntes Wissen einfließen lassen)
            from app.core.ocr_learning import get_learned_hints
            hints = get_learned_hints(ocr_text)
            for key, val in hints.items():
                if val and not data.get(key):
                    data[key] = val
                    logger.info(f"Auto-Learning: Feld {key} aus gelerntem Wissen vervollständigt.")
            
            # Post-Processing: Fuzzy Match & VAT Validation
            data["vendor_name"] = self._fuzzy_match_vendor(data.get("vendor_name", ""), ocr_text)
            data = self.validate_vat(data)
            
            logger.info(f"LLM Extraktion erfolgreich: {data.get('doctype', 'UNKNOWN')} (VAT: {data.get('vat_valid')})")
            return data
        except Exception as e:
            logger.error(f"Fehler bei LLM Extraktion: {e}")
            return {}

extraction_agent = ExtractionAgent()
