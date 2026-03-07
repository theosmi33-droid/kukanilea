from __future__ import annotations

from typing import Any

from app.agents.memory_store import MemoryManager
from flask import current_app, g


def get_tenant_id(*, default: str | None = None) -> str | None:
    """Returns tenant context from Flask `g` with optional fallback."""
    tenant_id = g.get("tenant_id")
    if tenant_id:
        return str(tenant_id)
    return default


def get_auth_db() -> Any | None:
    """Returns shared auth DB extension if initialized."""
    return current_app.extensions.get("auth_db")


def build_memory_manager() -> MemoryManager | None:
    """Returns MemoryManager backed by auth DB path if available."""
    auth_db = get_auth_db()
    if not auth_db:
        return None
    return MemoryManager(str(auth_db.path))

