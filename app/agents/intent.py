from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.llm import LLMProvider


@dataclass
class IntentResult:
    intent: str
    confidence: float


class IntentParser:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def parse(self, message: str, allow_llm: bool = True) -> IntentResult:
        text = message.strip().lower()
        if not text:
            return IntentResult(intent="unknown", confidence=0.0)

        if re.search(r"\bwer ist\s+\d{3,}\b", text):
            return IntentResult(intent="customer_lookup", confidence=0.8)
        if re.search(r"\b(öffne|open|zeige)\b", text):
            return IntentResult(intent="open_token", confidence=0.9)
        if re.search(r"\b(suche|finde|search)\b", text):
            return IntentResult(intent="search", confidence=0.8)
        if re.search(r"\b(kunde|kdnr|kundennr|wer ist)\b", text):
            return IntentResult(intent="customer_lookup", confidence=0.7)
        if re.search(r"\b(zusammenfassung|summary|kurzfassung)\b", text):
            return IntentResult(intent="summary", confidence=0.6)
        if re.search(r"\b(review|prüfung|freigabe)\b", text):
            return IntentResult(intent="review", confidence=0.6)
        if re.search(r"\b(wetter|weather)\b", text):
            return IntentResult(intent="weather", confidence=0.6)
        if re.fullmatch(r"\d{3,6}", text):
            return IntentResult(intent="customer_lookup", confidence=0.6)
        if any(
            k in text
            for k in [
                "rechnung",
                "angebot",
                "vertrag",
                "mahnung",
                "lieferschein",
                "bestellung",
            ]
        ):
            return IntentResult(intent="search", confidence=0.55)
        if re.search(r"\b(index|reindex)\b", text):
            return IntentResult(intent="index", confidence=0.7)
        if re.search(r"\b(mail|email|entwurf)\b", text):
            return IntentResult(intent="mail", confidence=0.6)
        if re.search(r"\b(upload)\b", text):
            return IntentResult(intent="upload", confidence=0.6)

        if len(text.split()) <= 2:
            return IntentResult(intent="search", confidence=0.35)

        if not allow_llm:
            return IntentResult(intent="unknown", confidence=0.25)

        rewrite = self.llm.rewrite_query(message)
        intent = str(rewrite.get("intent", "unknown"))
        if intent in {"search", "open_token", "customer_lookup", "summary"}:
            return IntentResult(intent=intent, confidence=0.4)
        return IntentResult(intent="unknown", confidence=0.3)
