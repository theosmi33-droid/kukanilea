from __future__ import annotations

import json
import logging
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

    def plan(self, intent: str, message: str, tenant_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        Generates an execution plan by asking the LLM to think and choose a tool.
        Includes relevant semantic context from the Memory System.
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

        prompt = (
            "Du bist der KUKANILEA Fleet Orchestrator. Deine Aufgabe ist es, einen Ausführungsplan basierend auf der Nutzeranfrage zu erstellen.\n"
            "Nutze das ReAct-Format (Thought -> Action).\n\n"
            f"{relevant_context}\n\n"
            "VERFÜGBARE TOOLS:\n"
            f"{tools_str}\n\n"
            "REGELN:\n"
            "1. Antworte STRENG im JSON-Format für die Action.\n"
            "2. Das Format muss sein: Thought: [Deine Überlegung]\n"
            "Action: {\"tool\": \"name\", \"params\": {...}}\n"
            "3. Wenn kein Tool passt, antworte mit null für die Action.\n\n"
            f"INTENT: {intent}\n"
            f"NACHRICHT: {message}\n"
        )

        try:
            # We want temperature 0.0 for deterministic tool selection
            response = self.llm.complete(prompt, temperature=0.0)
            logger.debug(f"Planner raw response: {response}")

            if "Action:" in response:
                action_part = response.split("Action:")[1].strip()
                start_idx = action_part.find("{")
                end_idx = action_part.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    json_str = action_part[start_idx : end_idx + 1]
                    plan = json.loads(json_str)
                    if plan and "tool" in plan:
                        return plan

        except Exception as e:
            logger.error(f"Planner failed to generate plan: {e}")

        # Fallback for basic intents if LLM fails
        text = (message or "").lower()
        if "list files" in text or "dateien zeigen" in text:
            return {"tool": "filesystem_list", "params": {"path": "."}}

        return None
