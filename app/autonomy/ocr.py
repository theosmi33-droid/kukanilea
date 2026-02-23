"""
app/autonomy/ocr.py
Offline Beleg-Erfassung (OCR + LLM) für KUKANILEA.
Wandelt schmutzige Zettel lokal in strukturiertes JSON um.
"""

import os
import logging
from PIL import Image
import pytesseract
from app.ai_chat.engine import ask_local_ai

logger = logging.getLogger("kukanilea.ocr")

def process_dirty_note(image_path: str):
    """
    Liest ein Bild lokal aus und extrahiert Daten via 'Meister'-LLM.
    Messe-Modus: Bei einem Pfad, der 'demo' enthält, wird ein vordefinierter Scan genutzt.
    """
    try:
        if "demo" in image_path.lower():
            logger.info("MESSE-MODUS AKTIV: Nutze vordefinierten Demo-Scan.")
            with open("docs/demo/FAKE_OCR_RESULT.txt", "r") as f:
                text = f.read()
        else:
            # 1. OCR Extraktion
            text = pytesseract.image_to_string(Image.open(image_path))
            logger.info(f"OCR Scan erfolgreich ({len(text)} Zeichen)")
        
        # 2. LLM Strukturierung
        prompt = (
            "Du bist ein Daten-Extraktor für das Handwerk. Hier ist ein roher OCR-Scan eines Belegs. "
            "Extrahiere den Lieferanten, das Datum, die Gesamtsumme und die einzelnen Artikel. "
            "Antworte AUSSCHLIESSLICH in validem JSON-Format. "
            f"\n\nSCAN-TEXT:\n{text}"
        )
        
        json_result = ask_local_ai(prompt, tenant_id="SYSTEM_OCR")
        return json_result
        
    except Exception as e:
        logger.error(f"OCR/Extraction failed: {e}")
        return {"error": str(e)}
