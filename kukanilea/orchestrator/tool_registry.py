from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ToolRegistry:
    tools: Dict[str, List[str]] = field(default_factory=dict)

    def register(self, tool: str, agent_name: str) -> None:
        self.tools.setdefault(tool, []).append(agent_name)

    def list_tools(self) -> Dict[str, List[str]]:
        return self.tools
