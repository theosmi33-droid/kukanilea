from __future__ import annotations

import re
from dataclasses import dataclass

from kukanilea.agents import LLMAdapter


@dataclass
class IntentResult:
    intent: str
    confidence: float


class IntentParser:
    def __init__(self, llm: LLMAdapter) -> None:
        self.llm = llm

    def parse(self, message: str) -> IntentResult:
        text = message.strip().lower()
        if not text:
            return IntentResult(intent="unknown", confidence=0.0)

        if re.search(r"\b(öffne|open|zeige)\b", text):
            return IntentResult(intent="open_token", confidence=0.9)
        if re.search(r"\b(suche|finde|search)\b", text):
            return IntentResult(intent="search", confidence=0.8)
        if re.search(r"\b(kunde|kdnr|kundennr|wer ist)\b", text):
            return IntentResult(intent="customer_lookup", confidence=0.7)
        if re.search(r"\b(zusammenfassung|summary|kurzfassung)\b", text):
            return IntentResult(intent="summary", confidence=0.6)
        if re.fullmatch(r"\d{3,6}", text):
            return IntentResult(intent="customer_lookup", confidence=0.6)
        if any(k in text for k in ["rechnung", "angebot", "vertrag", "mahnung"]):
            return IntentResult(intent="search", confidence=0.55)
        if re.search(r"\b(index|reindex)\b", text):
            return IntentResult(intent="index", confidence=0.7)
        if re.search(r"\b(mail|email|entwurf)\b", text):
            return IntentResult(intent="mail", confidence=0.6)
        if re.search(r"\b(upload)\b", text):
            return IntentResult(intent="upload", confidence=0.6)

        mock = self.llm.complete(f"intent: {message}")
        if "search" in mock:
            return IntentResult(intent="search", confidence=0.4)
        return IntentResult(intent="unknown", confidence=0.3)
