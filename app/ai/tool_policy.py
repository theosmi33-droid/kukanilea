"""
Tool-Policy Enforcement für KUKANILEA AI.
Definiert, welche Aktionen ohne menschliche Bestätigung ausgeführt werden dürfen.
"""
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolDecision:
    tool_name: str
    args: dict[str, Any]
    requires_confirm: bool

# Tools, die nur Daten lesen und keine Bestätigung benötigen
SAFE_TOOLS = {
    "search_knowledge",
    "search_contacts",
    "search_documents",
    "list_tasks",
    "web_search"
}

def validate_tool_call(tool_name: str, args: dict[str, Any]) -> ToolDecision:
    """
    Entscheidet, ob ein Tool-Aufruf sicher ist oder ein 'Confirm-Gate' braucht.
    """
    requires_confirm = tool_name not in SAFE_TOOLS
    return ToolDecision(
        tool_name=tool_name,
        args=args,
        requires_confirm=requires_confirm
    )

def check_tool_permission(tool_name: str, args: dict) -> bool:
    """Legacy wrapper."""
    return tool_name in SAFE_TOOLS
