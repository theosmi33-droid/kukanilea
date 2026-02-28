from __future__ import annotations

import logging
from typing import Any

from app.agents.executor import AgentExecutor
from app.agents.planner import Planner

logger = logging.getLogger("kukanilea.agents.runtime")


class AgentRuntime:
    """
    Main runtime for agentic workflows.
    Orchestrates planning and execution.
    """

    def __init__(self):
        self.executor = AgentExecutor()
        self.planner = Planner()

    def run(self, intent: str, message: str, tenant_id: str = "default") -> Any:
        logger.info(f"AgentRuntime processing intent: {intent} for tenant: {tenant_id}")
        plan = self.planner.plan(intent, message, tenant_id=tenant_id)

        if not plan:
            logger.warning(f"No plan found for intent: {intent}")
            return {"error": "Kein Ausführungsplan gefunden."}

        try:
            result = self.executor.execute(plan["tool"], plan["params"])
            return result
        except Exception as e:
            logger.error(f"AgentRuntime execution error: {e}")
            return {"error": str(e)}
