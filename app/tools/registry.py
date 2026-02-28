from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_tool import BaseTool


class ToolRegistry:
    """
    Central registry for KUKANILEA tools.
    Allows for automatic discovery and safe execution.
    """

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self.tools.get(name)

    def list(self) -> List[str]:
        return list(self.tools.keys())


registry = ToolRegistry()
