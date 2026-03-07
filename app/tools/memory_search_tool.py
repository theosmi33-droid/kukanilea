from __future__ import annotations

from typing import Any, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.tools.shared_services import build_memory_manager, get_tenant_id


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
        tenant_id = get_tenant_id()
        if not tenant_id:
            return {"error": "No tenant context found."}

        manager = build_memory_manager()
        if not manager:
            return {"error": "Database not initialized."}

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
