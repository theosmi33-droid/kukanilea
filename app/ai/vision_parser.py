"""
app/ai/vision_parser.py
Lokaler Offline Vision Agent für KUKANILEA.
Nutzt Moondream (via transformers) für effiziente Bildanalyse auf lokaler Hardware.
"""

import os
import logging
from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger("kukanilea.vision")

class VisionParser:
    _instance = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VisionParser, cls).__new__(cls)
        return cls._instance

    def _get_model(self):
        if self._model is None:
            model_id = "vikhyatk/moondream2"
            revision = "2024-08-05" # Nutze eine stabile Revision
            logger.info(f"Lade Vision Modell {model_id}...")
            
            # Moondream ist extrem klein (~1.6B Parameter) und läuft gut auf CPU
            self._model = AutoModelForCausalLM.from_pretrained(
                model_id, trust_remote_code=True, revision=revision
            )
            self._tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
            
        return self._model, self._tokenizer

    def analyze_image(self, image_path: str, prompt: str = "Beschreibe den Defekt oder das Bauteil auf diesem Foto für einen Handwerker präzise.") -> str:
        """Analysiert ein Bild lokal und generiert eine Textbeschreibung."""
        if os.environ.get("KUKANILEA_DISABLE_MOONDREAM") == "1":
            logger.warning("Moondream2 ist aufgrund von Hardware-Limits deaktiviert.")
            return "Moondream2 deaktiviert (RAM Limit)."

        try:
            model, tokenizer = self._get_model()
            image = Image.open(image_path)
            
            # Moondream spezifische Inferenz
            enc_image = model.encode_image(image)
            description = model.answer_question(enc_image, prompt, tokenizer)
            
            logger.info(f"Bildanalyse abgeschlossen: {description[:50]}...")
            return description.strip()
        except Exception as e:
            logger.error(f"Fehler bei der Bildanalyse: {e}")
            # Fallback für Prototyping/Messe-Modus falls Modell-Download fehlschlägt
            if "demo" in image_path.lower():
                return "Defektes Eckventil an einer Waschbeckenarmatur, Kalkablagerungen sichtbar."
            return f"Fehler bei Bildanalyse: {str(e)}"

vision_parser = VisionParser()
