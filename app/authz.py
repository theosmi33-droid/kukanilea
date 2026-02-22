import functools
from collections.abc import Callable

from fastapi import HTTPException, Request


class SecurityContext:
    def __init__(self, tenant_id: str, user_id: str, role: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role


def get_current_security_context(request: Request) -> SecurityContext:
    """
    Extracts security context from headers.
    In production, this would validate a JWT or session cookie.
    """
    # Deny-by-default baseline
    tenant_id = request.headers.get("X-Tenant-ID")
    user_id = request.headers.get("X-User-ID", "anonymous")
    role = request.headers.get("X-Role", "GUEST")

    if not tenant_id:
        # PII-safe logging of AuthZ failure
        # logger.warning("Missing tenant_id in request")
        raise HTTPException(
            status_code=401, detail="Authentication required (Tenant ID missing)"
        )

    return SecurityContext(tenant_id, user_id, role)


def require_role(allowed_roles: list[str]):
    """Decorator for server-side RBAC enforcement."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            ctx = kwargs.get("ctx")
            if not ctx:
                # Search in dependencies
                for val in kwargs.values():
                    if isinstance(val, SecurityContext):
                        ctx = val
                        break

            if not ctx or ctx.role not in allowed_roles:
                raise HTTPException(
                    status_code=403, detail="Forbidden: Insufficient permissions"
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
