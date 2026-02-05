from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class IntentResult:
    intent: str
    confidence: float


class IntentParser:
    def parse(self, message: str) -> IntentResult:
        text = message.strip().lower()
        if not text:
            return IntentResult(intent="unknown", confidence=0.0)

        if re.search(r"\b(öffne|open|zeige|view)\b", text) or re.search(r"[a-f0-9]{16,64}", text):
            return IntentResult(intent="open_token", confidence=0.9)
        if re.search(r"\b(suche|finde|search|suche nach|fnd)\b", text):
            return IntentResult(intent="search", confidence=0.85)
        if re.search(r"\b(kunde|kdnr|kundennr|wer ist|kunde ist)\b", text):
            return IntentResult(intent="customer_lookup", confidence=0.8)
        if re.search(r"\b(zusammenfassung|summary|kurzfassung|fass zusammen)\b", text):
            return IntentResult(intent="summary", confidence=0.7)
        if re.search(r"\b(review|freigabe|prüfung|ablage)\b", text):
            return IntentResult(intent="review", confidence=0.7)
        if re.search(r"\b(archiv|archivieren|ablegen)\b", text):
            return IntentResult(intent="archive", confidence=0.65)
        if re.fullmatch(r"\d{3,6}", text):
            return IntentResult(intent="customer_lookup", confidence=0.6)
        if any(k in text for k in ["rechnung", "angebot", "vertrag", "mahnung", "lieferschein"]):
            return IntentResult(intent="search", confidence=0.6)
        if re.search(r"\b(index|reindex|neu index|neu indizieren)\b", text):
            return IntentResult(intent="index", confidence=0.75)
        if re.search(r"\b(mail|email|entwurf|antwort|anschreiben)\b", text):
            return IntentResult(intent="mail", confidence=0.65)
        if re.search(r"\b(upload|hochladen|einreichen)\b", text):
            return IntentResult(intent="upload", confidence=0.65)
        if re.search(r"\b(wetter|temperatur|regen|wind)\b", text):
            return IntentResult(intent="weather", confidence=0.6)

        return IntentResult(intent="unknown", confidence=0.3)
