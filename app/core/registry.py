"""
app/core/registry.py
Strict Module Registry for KUKANILEA.
Replaces auto-discovery with explicit registration for stability and security.
"""
import logging
from typing import Dict, Any, List, Type

logger = logging.getLogger("kukanilea.registry")

class ComponentRegistry:
    def __init__(self):
        self._agents: Dict[str, Any] = {}
        self._tools: Dict[str, Any] = {}
        self._services: Dict[str, Any] = {}

    def register_agent(self, agent_id: str, agent_class: Type):
        self._agents[agent_id] = agent_class
        logger.info(f"Registered Agent: {agent_id}")

    def register_tool(self, tool_id: str, func: Any):
        self._tools[tool_id] = func
        logger.info(f"Registered Tool: {tool_id}")

    def register_service(self, service_id: str, instance: Any):
        self._services[service_id] = instance
        logger.info(f"Registered Service: {service_id}")

    def get_agent(self, agent_id: str) -> Optional[Type]:
        return self._agents.get(agent_id)

    def get_tool(self, tool_id: str) -> Optional[Any]:
        return self._tools.get(tool_id)

    def get_all_agents(self) -> Dict[str, Type]:
        return self._agents.copy()

# Global Singleton
registry = ComponentRegistry()
