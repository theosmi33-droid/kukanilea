from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from app.agents.llm import get_default_provider
from app.tools.registry import registry
from app.agents.context_manager import ContextManager

logger = logging.getLogger("kukanilea.agents.planner")


class Planner:
    """
    Agentic Planner using local LLM (Ollama) and the ReAct pattern.
    Maps user intents and messages to specific tool execution plans.
    """

    def __init__(self, llm_provider=None):
        self.llm = llm_provider or get_default_provider()

    def plan(self, intent: str, message: str, tenant_id: str = "default", history: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Generates an execution plan by asking the LLM to think and choose a tool.
        Includes relevant semantic context from the Memory System and history of previous steps.
        """
        # 1. Retrieve Context
        ctx_manager = ContextManager(tenant_id)
        relevant_context = ctx_manager.get_relevant_context(message)

        # 2. Get Available Tools
        available_tools = registry.list()
        tool_descriptions = []
        for name in available_tools:
            t = registry.get(name)
            if t:
                tool_descriptions.append(f"- {name}: {t.description} (Schema: {t.input_schema})")

        tools_str = "\n".join(tool_descriptions)

        # 3. Format History
        history_str = ""
        if history:
            history_str = "\n".join([
                f"Thought: {h.get('thought')}\nAction: {h.get('action')}({h.get('params')})\nObservation: {h.get('observation')}"
                for h in history
            ])

        prompt = (
            "Du bist der KUKANILEA Fleet Orchestrator. Deine Aufgabe ist es, einen Ausführungsplan basierend auf der Nutzeranfrage zu erstellen.\n"
            "Nutze das ReAct-Format (Thought -> Action -> Observation).\n\n"
            f"KONTEXT:\n{relevant_context}\n\n"
            f"VERLAUF:\n{history_str}\n\n"
            "VERFÜGBARE TOOLS:\n"
            f"{tools_str}\n\n"
            "REGELN:\n"
            "1. Antworte STRENG im JSON-Format für die Action.\n"
            "2. Das Format muss sein: Thought: [Deine Überlegung]\n"
            "Action: {\"tool\": \"name\", \"params\": {...}}\n"
            "3. Wenn du fertig bist, nutze das Tool 'final_answer' mit der Antwort.\n\n"
            f"INTENT: {intent}\n"
            f"NACHRICHT: {message}\n"
        )

        try:
            # We want temperature 0.0 for deterministic tool selection
            response = self.llm.complete(prompt, temperature=0.0)
            logger.debug(f"Planner raw response: {response}")

            thought = ""
            if "Thought:" in response:
                thought = response.split("Thought:")[1].split("Action:")[0].strip()

            if "Action:" in response:
                action_part = response.split("Action:")[1].strip()
                start_idx = action_part.find("{")
                end_idx = action_part.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    json_str = action_part[start_idx : end_idx + 1]
                    plan = json.loads(json_str)
                    if plan and "tool" in plan:
                        plan["thought"] = thought
                        return plan

        except Exception as e:
            logger.error(f"Planner failed to generate plan: {e}")

        # Fallback for basic intents if LLM fails
        text = (message or "").lower()
        deterministic = self._deterministic_plan(intent=intent, message=message)
        if deterministic:
            return deterministic
        if "list files" in text or "dateien zeigen" in text:
            return {"tool": "filesystem_list", "params": {"path": "."}}

        return None

    def _deterministic_plan(self, intent: str, message: str) -> Optional[Dict[str, Any]]:
        text = (message or "").strip().lower()
        if not text:
            return None

        if intent in {"search", "mail"} and (" und " in text or "danach" in text):
            return {
                "tool": "react_chain",
                "params": {
                    "steps": [
                        {"connector": "internal", "action": "receive"},
                        {"tool": "search_docs", "reason": "context_lookup"},
                        {"tool": "mail_generate", "reason": "draft_reply"},
                    ],
                    "confirm_gate": True,
                },
            }

        if "telegram" in text or "instagram" in text or "whatsapp" in text or "messenger" in text:
            provider = self._extract_provider(text)
            return {
                "tool": "messenger_connector",
                "params": {
                    "provider": provider,
                    "interface": ["send", "receive", "sync", "status"],
                    "mode": "business_only" if provider in {"whatsapp", "meta"} else "standard",
                    "confirm_gate": True,
                },
            }

        if re.search(r"\b(task|aufgabe|termin|kalender)\b", text):
            return {
                "tool": "message_to_work_item",
                "params": {
                    "target": "termin" if "termin" in text or "kalender" in text else "task",
                    "confirm_gate": True,
                },
            }
        return None

    def _extract_provider(self, text: str) -> str:
        if "telegram" in text:
            return "telegram"
        if "whatsapp" in text:
            return "whatsapp"
        if "instagram" in text:
            return "instagram"
        if "messenger" in text or "meta" in text or "facebook" in text:
            return "meta"
        return "internal"
