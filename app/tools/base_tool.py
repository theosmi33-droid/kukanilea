from __future__ import annotations

from typing import Any, Dict


class BaseTool:
    """
    Base class for all KUKANILEA tools.
    Inspired by llm-engineer-toolkit patterns.
    """

    name = "base"
    description = ""
    input_schema: Dict[str, Any] = {}

    def run(self, **kwargs) -> Any:
        raise NotImplementedError("Tools must implement the run method.")
