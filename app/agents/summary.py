from __future__ import annotations

import json
import logging
from typing import List

from pydantic import BaseModel, Field

from app.agents.guards import neutralize_untrusted_text
from app.agents.observer import ObserverAgent

from .base import AgentContext, AgentResult, BaseAgent

logger = logging.getLogger("kukanilea.agents.summary")


class SummaryOutput(BaseModel):
    title: str = Field(..., description="Kurzer Titel des Dokuments")
    key_points: List[str] = Field(..., description="Liste von 3-5 Kernpunkten")
    sentiment: str = Field(
        ..., description="Stimmung des Dokuments (positiv, neutral, negativ)"
    )


class SummaryAgent(BaseAgent):
    name = "summary"
    required_role = "ADMIN"
    scope = "summary"
    tools = ["summarize_doc"]

    def __init__(self, core_module, llm_provider=None) -> None:
        self.core = core_module
        self.llm = llm_provider
        self.observer = ObserverAgent()

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "summary"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        token = context.token
        if not token:
            return AgentResult(
                text="Bitte gib einen Token an, den ich zusammenfassen soll."
            )
        payload = None
        if callable(getattr(self.core, "read_done", None)):
            payload = self.core.read_done(token)
        if payload is None and callable(getattr(self.core, "read_pending", None)):
            payload = self.core.read_pending(token)
        if not payload:
            return AgentResult(text="Dokument nicht gefunden.")
        text = str(payload.get("text") or payload.get("extracted_text") or "")
        if not text:
            text = json.dumps(payload, ensure_ascii=False)
        safe_text = neutralize_untrusted_text(text)

        if self.llm and getattr(self.llm, "available", False):
            prompt = (
                "Du bist ein Dokumenten-Analyst. Analysiere den folgenden Text und gib eine strukturierte Zusammenfassung in JSON aus.\n"
                "Das JSON muss exakt dieses Format haben: "
                '{"title": "...", "key_points": ["...", "..."], "sentiment": "..."}\n'
                f"Text:\n{safe_text[:2000]}"
            )

            # Use Observer for Veto & Retry logic
            validated_output = self.observer.veto_and_retry(
                prompt, SummaryOutput, self.llm.complete
            )

            if validated_output:
                res_text = f"### {validated_output.title}\n\n"
                res_text += "**Kernpunkte:**\n"
                for kp in validated_output.key_points:
                    res_text += f"- {kp}\n"
                res_text += f"\n**Stimmung:** {validated_output.sentiment}"
                return AgentResult(text=res_text, data=validated_output.model_dump())
            else:
                # Fallback to legacy summarize if observer vetoed everything
                summary = self.llm.summarize(safe_text)
        else:
            summary = safe_text.strip()[:400]

        return AgentResult(text=summary)
