from __future__ import annotations

from typing import Any, Dict, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.agents.memory_store import MemoryManager
from flask import current_app, g

class MemorySearchTool(BaseTool):
    """
    Searches for information in the semantic long-term memory.
    """

    name = "memory_search"
    description = "Sucht semantisch nach relevantem Kontext in alten Gesprächen oder Dokumenten."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Die Suchanfrage."},
            "limit": {"type": "integer", "default": 5, "description": "Anzahl der Treffer."},
            "topic": {"type": "string", "description": "Optionales Topic für gezielte Memory-Abfrage."},
            "recency_days": {"type": "integer", "default": 60, "description": "Zeitfenster für Recency-Ranking."}
        },
        "required": ["query"]
    }

    def run(self, query: str, limit: int = 5, topic: Optional[str] = None, recency_days: int = 60) -> Any:
        tenant_id = g.get("tenant_id")
        if not tenant_id:
            return {"error": "No tenant context found."}

        auth_db = current_app.extensions.get("auth_db")
        if not auth_db:
            return {"error": "Database not initialized."}

        manager = MemoryManager(str(auth_db.path))
        if topic:
            results = manager.retrieve_by_topic(
                tenant_id=tenant_id,
                topic=topic,
                limit=limit,
                recency_days=recency_days,
            )
            return {"results": results, "topic": topic, "retrieval": "topic_recency"}

        results = manager.retrieve_context(tenant_id, query, limit)
        return {"results": results, "retrieval": "semantic"}

# Register tool
registry.register(MemorySearchTool())
