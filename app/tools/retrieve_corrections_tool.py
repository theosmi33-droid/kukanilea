from __future__ import annotations

from typing import Any, Dict, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.agents.memory_store import MemoryManager
from flask import current_app, g

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
        tenant_id = g.get("tenant_id")
        if not tenant_id:
            return {"error": "No tenant context found."}
            
        auth_db = current_app.extensions.get("auth_db")
        if not auth_db:
            return {"error": "Database not initialized."}
            
        manager = MemoryManager(str(auth_db.path))
        # We search specifically for memories of type 'ocr_correction'
        all_hits = manager.retrieve_context(tenant_id, query, limit=10)
        
        corrections = [
            hit for hit in all_hits 
            if hit.get("metadata", {}).get("type") == "ocr_correction"
        ]
        
        return {"corrections": corrections[:limit]}

# Register tool
registry.register(RetrieveCorrectionsTool())
