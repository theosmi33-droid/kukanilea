"""
app/core/ocr_learning.py
Auto-Learning System für die OCR-Extraktion.
Speichert Nutzer-Korrekturen als neue Vorlagen oder Few-Shot-Beispiele.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("kukanilea.ocr_learning")

LEARNED_TEMPLATES_PATH = Path("instance/identity/learned_ocr_templates.json")

def record_correction(original_data: Dict[str, Any], corrected_data: Dict[str, Any], ocr_text: str):
    """
    Vergleicht Original-KI-Extraktion mit Nutzer-Korrektur und speichert Differenzen.
    """
    diff = {}
    important_fields = ["vendor_name", "doctype", "invoice_no", "total_amount", "doc_date"]
    
    changed = False
    for field in important_fields:
        orig = str(original_data.get(field) or "").strip()
        corr = str(corrected_data.get(field) or "").strip()
        if corr and orig != corr:
            diff[field] = corr
            changed = True
            
    if not changed:
        return # Keine Korrektur nötig

    # Wir speichern die Korrektur zusammen mit einem Text-Schnipsel (Anker)
    # um das Layout beim nächsten Mal wiederzuerkennen.
    learning_entry = {
        "vendor_name": corrected_data.get("vendor_name"),
        "corrections": diff,
        "anchor_text": ocr_text[:500], # Die ersten 500 Zeichen als Fingerabdruck
        "timestamp": os.environ.get("CURRENT_TIME", "")
    }

    _save_learning_entry(learning_entry)

def _save_learning_entry(entry: Dict[str, Any]):
    try:
        LEARNED_TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        data = []
        if LEARNED_TEMPLATES_PATH.exists():
            with open(LEARNED_TEMPLATES_PATH, "r") as f:
                data = json.load(f)
        
        # Dubletten-Check (nach vendor_name)
        # Für den Prototyp: Wir hängen einfach an. Später: Clustering.
        data.append(entry)
        
        # Limit auf 100 Lern-Einträge zur Performance-Schonung
        data = data[-100:]
        
        with open(LEARNED_TEMPLATES_PATH, "w") as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Auto-Learning: Neue Korrektur für {entry.get('vendor_name')} gelernt.")
    except Exception as e:
        logger.error(f"Fehler beim Speichern des Lern-Eintrags: {e}")

def get_learned_hints(ocr_text: str) -> Dict[str, Any]:
    """
    Sucht in gelernten Vorlagen nach Übereinstimmungen für den aktuellen OCR-Text.
    """
    if not LEARNED_TEMPLATES_PATH.exists():
        return {}

    try:
        with open(LEARNED_TEMPLATES_PATH, "r") as f:
            data = json.load(f)
            
        # Einfacher Fingerabdruck-Abgleich (In Prod: Vektor-Suche)
        for entry in reversed(data):
            anchor = entry.get("anchor_text", "")
            if anchor and anchor[:100] in ocr_text:
                logger.info(f"Auto-Learning: Bekanntes Layout erkannt ({entry.get('vendor_name')})")
                return entry.get("corrections", {})
    except Exception as e:
        logger.error(f"Fehler beim Laden gelernter Hints: {e}")
        
    return {}
