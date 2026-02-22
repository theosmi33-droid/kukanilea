from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolRegistry:
    tools: dict[str, list[str]] = field(default_factory=dict)

    def register(self, tool: str, agent_name: str) -> None:
        self.tools.setdefault(tool, []).append(agent_name)

    def list_tools(self) -> dict[str, list[str]]:
        return self.tools
