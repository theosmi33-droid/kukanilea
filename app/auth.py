from __future__ import annotations

import functools
import hashlib
import secrets
import time
from typing import Optional

from flask import abort, current_app, g, redirect, request, session, url_for

from .db import AuthDB, Membership
from .errors import json_error

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_auth(app, db: AuthDB) -> None:
    app.before_request(lambda: _load_user(db))
    app.before_request(lambda: _enforce_session_permissions(db))


def _load_user(db: AuthDB) -> None:
    g.user = session.get("user")
    g.role = session.get("role")
    g.tenant_id = session.get("tenant_id")
    if g.user and not g.tenant_id:
        memberships = db.get_memberships(g.user)
        if memberships:
            session["tenant_id"] = memberships[0].tenant_id
            session["role"] = memberships[0].role
            g.role = memberships[0].role
            g.tenant_id = memberships[0].tenant_id




def _is_public_path(path: str) -> bool:
    public_prefixes = (
        "/static/",
        "/health",
        "/api/health",
        "/api/ping",
        "/login",
        "/logout",
        "/forgot",
        "/reset-code",
        "/password-reset",
    )
    return any(path.startswith(prefix) for prefix in public_prefixes)


def _enforce_session_permissions(db: AuthDB):
    user = current_user()
    if not user:
        return None
    path = request.path or "/"
    if _is_public_path(path):
        return None

    role = current_role()
    tenant_id = current_tenant()
    if role == "DEV":
        return None

    memberships = db.get_memberships(user)
    if not memberships:
        current_app.logger.warning("Access denied: user has no memberships", extra={"user": user, "path": path})
        session.clear()
        if path.startswith("/api/"):
            return json_error("forbidden", "Nicht erlaubt.", status=403)
        return redirect(url_for("web.login", next=path))

    allowed = any(m.tenant_id == tenant_id and policy_allows(m, "READONLY") for m in memberships)
    if allowed:
        return None

    current_app.logger.warning("Access denied: invalid tenant/role context", extra={"user": user, "tenant": tenant_id, "path": path})
    session.clear()
    if path.startswith("/api/"):
        return json_error("forbidden", "Nicht erlaubt.", status=403)
    return redirect(url_for("web.login", next=path))


def login_user(username: str, role: str, tenant_id: str) -> None:
    now = time.time()
    session["user"] = username
    session["role"] = role
    session["tenant_id"] = tenant_id
    session["last_active"] = now
    session["issued_at"] = now
    session["session_rotated_at"] = now
    session["session_nonce"] = secrets.token_urlsafe(24)


def logout_user() -> None:
    session.clear()


def current_user() -> Optional[str]:
    return session.get("user")


def current_role() -> str:
    if session.get("user") == "dev":
        return "DEV"
    return session.get("role") or "READONLY"


def current_tenant() -> str:
    # Dev can act within any tenant
    return session.get("tenant_id") or ""


def login_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return json_error(
                    "auth_required", "Authentifizierung erforderlich.", status=401
                )
            return redirect(url_for("web.login", next=request.path))
        return func(*args, **kwargs)

    return wrapper


def require_role(min_role: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                role = current_role()
                if role not in ROLE_ORDER:
                    role = "READONLY"
                required = min_role if min_role in ROLE_ORDER else "READONLY"
                if ROLE_ORDER.index(role) < ROLE_ORDER.index(required):
                    if request.path.startswith("/api/"):
                        return json_error("forbidden", "Nicht erlaubt.", status=403)
                    abort(403)
            except ValueError:
                if request.path.startswith("/api/"):
                    return json_error("forbidden", "Nicht erlaubt.", status=403)
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def policy_allows(membership: Membership, required: str) -> bool:
    try:
        role = membership.role if membership.role in ROLE_ORDER else "READONLY"
        required_role = required if required in ROLE_ORDER else "READONLY"
        return ROLE_ORDER.index(role) >= ROLE_ORDER.index(required_role)
    except ValueError:
        return False
