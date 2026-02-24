"""
app/ai/voice_parser.py
Offline Spracherkennung für KUKANILEA.
Nutzt faster-whisper mit dem 'tiny' Modell für minimale RAM-Belastung.
"""

import os
import logging
from pathlib import Path
from faster_whisper import WhisperModel

logger = logging.getLogger("kukanilea.voice")

class VoiceParser:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VoiceParser, cls).__new__(cls)
        return cls._instance

    def _get_model(self):
        if self._model is None:
            logger.info("Lade Whisper 'tiny' Modell für lokale Transkription...")
            # 'tiny' Modell ist extrem klein (~75MB) und schnell auf CPU/GPU
            # device="cpu" stellt sicher, dass es auf jedem Handwerker-Laptop läuft
            # compute_type="int8" spart zusätzlich RAM
            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio_path: str) -> str:
        """Transkribiert eine lokale Audio-Datei in Text."""
        try:
            model = self._get_model()
            segments, info = model.transcribe(audio_path, beam_size=5, language="de")
            
            full_text = " ".join([segment.text for segment in segments]).strip()
            logger.info(f"Spracherkennung abgeschlossen (Sprache: {info.language}, Wahrscheinlichkeit: {info.language_probability:.2f})")
            return full_text
        except Exception as e:
            logger.error(f"Fehler bei der Spracherkennung: {e}")
            return ""

voice_parser = VoiceParser()
