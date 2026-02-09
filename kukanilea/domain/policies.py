from __future__ import annotations


def require_tenant(tenant_id: str) -> None:
    if not tenant_id:
        raise ValueError("tenant_required")
