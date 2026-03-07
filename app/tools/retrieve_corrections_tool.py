from __future__ import annotations

from typing import Any

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.tools.shared_services import build_memory_manager, get_tenant_id


class RetrieveCorrectionsTool(BaseTool):
    """
    Retrieves past user corrections from the semantic memory.
    Helps agents avoid repeating the same extraction mistakes.
    """

    name = "retrieve_corrections"
    description = "Sucht im Gedächtnis nach früheren manuellen Korrekturen zu ähnlichen Dokumenten."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Suchbegriff oder Textauszug des aktuellen Dokuments."},
            "limit": {"type": "integer", "default": 3}
        },
        "required": ["query"]
    }

    def run(self, query: str, limit: int = 3) -> Any:
        tenant_id = get_tenant_id()
        if not tenant_id:
            return {"error": "No tenant context found."}

        manager = build_memory_manager()
        if not manager:
            return {"error": "Database not initialized."}

        # We search specifically for memories of type 'ocr_correction'
        all_hits = manager.retrieve_context(tenant_id, query, limit=10)

        corrections = [
            hit for hit in all_hits
            if hit.get("metadata", {}).get("type") == "ocr_correction"
        ]

        return {"corrections": corrections[:limit]}


# Register tool
registry.register(RetrieveCorrectionsTool())
