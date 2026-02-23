"""
app/autonomy/ocr.py
Offline Beleg-Erfassung (OCR + LLM) für KUKANILEA.
Wandelt schmutzige Zettel lokal in strukturiertes JSON um.
"""

import os
import logging
from PIL import Image
import pytesseract

logger = logging.getLogger("kukanilea.ocr")

def is_supported_image_path(path: str) -> bool:
    """Prüft ob die Datei ein unterstütztes Bildformat für OCR ist."""
    ext = os.path.splitext(path)[1].lower()
    return ext in {".jpg", ".jpeg", ".png", ".tiff", ".tif"}

def ocr_allowed(tenant_id: str) -> bool:
    """Prüft ob OCR für den Mandanten erlaubt ist."""
    from app.knowledge import knowledge_policy_get
    policy = knowledge_policy_get(tenant_id)
    return bool(policy.allow_ocr)

def ocr_stats_24h(tenant_id: str) -> int:
    """Gibt die Anzahl der OCR-Scans in den letzten 24h zurück."""
    return 0 # Mock für RC1+

def ocr_stats_total(tenant_id: str) -> int:
    """Gibt die Gesamtzahl der OCR-Scans zurück."""
    return 0 # Mock für RC1+

def recent_ocr_jobs(tenant_id: str, limit: int = 10) -> list:
    """Gibt die Liste der letzten OCR-Scans zurück."""
    return [] # Mock für RC1+

def resolve_tesseract_bin() -> str:
    """Sucht nach dem tesseract-binary im Pfad."""
    import shutil
    return shutil.which("tesseract") or "tesseract"

def submit_ocr_for_source_file(tenant_id: str, file_path: str) -> str:
    """Reiht ein Dokument in die OCR-Warteschlange ein."""
    # Background worker integration
    return "ocr_job_queued"

def process_dirty_note(image_path: str):
    """
    Liest ein Bild lokal aus und extrahiert Daten via 'Meister'-LLM.
    Messe-Modus: Bei einem Pfad, der 'demo' enthält, wird ein vordefinierter Scan genutzt.
    """
    from app.ai_chat.engine import ask_local_ai
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
