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
            "metadata": {"type": "object", "description": "Optionale Zusatzmetadaten."},
            "topic": {"type": "string", "description": "Fachthema der Knowledge Memory."},
            "memory_type": {"type": "string", "description": "Typ: note|preference|contact_reference.", "default": "note"},
            "confirm_write": {"type": "boolean", "default": False, "description": "Explizite Bestätigung für Schreibzugriff."}
        },
        "required": ["content", "topic"]
    }

    def run(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        topic: str = "general",
        memory_type: str = "note",
        confirm_write: bool = False,
    ) -> Any:
        tenant_id = g.get("tenant_id")
        if not tenant_id:
            return {"error": "No tenant context found."}

        auth_db = current_app.extensions.get("auth_db")
        if not auth_db:
            return {"error": "Database not initialized."}

        manager = MemoryManager(str(auth_db.path))
        return manager.store_knowledge_memory(
            tenant_id=tenant_id,
            content=content,
            topic=topic,
            memory_type=memory_type,
            actor="agent",
            confirm_write=bool(confirm_write),
            metadata=metadata,
        )

# Register tool
registry.register(MemoryStoreTool())
