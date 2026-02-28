from __future__ import annotations

from typing import Any, Dict, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.agents.memory_store import MemoryManager
from flask import current_app, g

class MemoryStoreTool(BaseTool):
    """
    Stores information in the semantic long-term memory.
    """

    name = "memory_store"
    description = "Speichert eine Information dauerhaft im Gedächtnis des Systems."
    input_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Die zu speichernde Information."},
            "metadata": {"type": "object", "description": "Optionale Zusatzmetadaten."}
        },
        "required": ["content"]
    }

    def run(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Any:
        tenant_id = g.get("tenant_id")
        if not tenant_id:
            return {"error": "No tenant context found."}
            
        auth_db = current_app.extensions.get("auth_db")
        if not auth_db:
            return {"error": "Database not initialized."}
            
        manager = MemoryManager(str(auth_db.path))
        success = manager.store_memory(tenant_id, "agent", content, metadata)
        
        return {"status": "stored" if success else "failed"}

# Register tool
registry.register(MemoryStoreTool())
