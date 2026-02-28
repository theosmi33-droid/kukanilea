from __future__ import annotations

import logging
from typing import Any, Dict

from app.tools.registry import registry

logger = logging.getLogger("kukanilea.agents.executor")


class AgentExecutor:
    """
    Executes tools requested by agents with validation and logging.
    """

    def execute(self, tool_name: str, params: Dict[str, Any]) -> Any:
        tool = registry.get(tool_name)
        if not tool:
            logger.error(f"Execution failed: Tool '{tool_name}' not found.")
            raise ValueError(f"Tool '{tool_name}' not found in registry.")

        logger.info(f"Executing tool: {tool_name} with params: {params}")
        try:
            return tool.run(**params)
        except Exception as e:
            logger.exception(f"Error during tool execution '{tool_name}': {e}")
            return {"error": str(e)}
