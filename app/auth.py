from __future__ import annotations

import functools
import hashlib
import hmac
import secrets
from typing import Optional

from flask import abort, g, redirect, request, session, url_for

from .db import AuthDB, Membership
from .errors import json_error
from .rbac import LEGACY_ROLE_ORDER, legacy_role_from_roles, normalize_role_name

ROLE_ORDER = LEGACY_ROLE_ORDER


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 210000
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    value = str(stored_hash or "")
    if value.startswith("pbkdf2_sha256$"):
        parts = value.split("$", 3)
        if len(parts) != 4:
            return False
        try:
            iterations = int(parts[1])
            salt_hex = parts[2]
            expected = parts[3]
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations
            ).hex()
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False
    # Legacy fallback for existing SHA256 user rows.
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, value)


def init_auth(app, db: AuthDB) -> None:
    app.before_request(lambda: _load_user(db))


def _load_user(db: AuthDB) -> None:
    g.user = session.get("user")
    g.role = session.get("role")
    g.tenant_id = session.get("tenant_id")
    g.roles = []
    g.permissions = set()
    if g.user and not g.tenant_id:
        memberships = db.get_memberships(g.user)
        if memberships:
            session["tenant_id"] = memberships[0].tenant_id
            session["role"] = memberships[0].role
            g.role = memberships[0].role
            g.tenant_id = memberships[0].tenant_id
    if g.user:
        legacy = str(g.role or "").strip().upper()
        roles = db.ensure_user_rbac_roles(g.user, legacy_role=legacy)
        perms = db.get_effective_permissions_for_roles(roles)
        g.roles = roles
        g.permissions = perms
        session["rbac_roles"] = roles
        session["rbac_perms"] = sorted(perms)
        effective_role = legacy_role_from_roles(roles, fallback=legacy or "READONLY")
        session_role = str(session.get("role") or "").strip().upper()
        if session_role not in ROLE_ORDER:
            session_role = effective_role
            session["role"] = session_role
        g.role = session_role


def login_user(username: str, role: str, tenant_id: str) -> None:
    session["user"] = username
    session["role"] = role
    session["tenant_id"] = tenant_id


def logout_user() -> None:
    session.clear()


def current_user() -> Optional[str]:
    return session.get("user")


def current_role() -> str:
    role = str(session.get("role") or "").strip().upper()
    if role in ROLE_ORDER:
        return role
    normalized = normalize_role_name(role)
    return legacy_role_from_roles([normalized], fallback="READONLY")


def current_roles() -> list[str]:
    if getattr(g, "roles", None):
        return list(g.roles)
    rows = session.get("rbac_roles")
    if isinstance(rows, list):
        return [normalize_role_name(str(r or "")) for r in rows]
    normalized = normalize_role_name(current_role())
    return [normalized] if normalized else []


def has_permission(permission: str) -> bool:
    token = str(permission or "").strip()
    if not token or not current_user():
        return False
    perms = getattr(g, "permissions", None)
    if isinstance(perms, set):
        return "*" in perms or token in perms
    raw = session.get("rbac_perms")
    if isinstance(raw, list):
        perm_set = {str(p) for p in raw}
        return "*" in perm_set or token in perm_set
    return False


def current_tenant() -> str:
    ctx = getattr(g, "tenant_ctx", None)
    tenant_id = str(getattr(ctx, "tenant_id", "") or "").strip()
    if tenant_id:
        return tenant_id
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


def require_permission(permission: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not has_permission(permission):
                if request.path.startswith("/api/"):
                    return json_error("forbidden", "Nicht erlaubt.", status=403)
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(permissions: list[str]):
    needed = [str(p).strip() for p in permissions if str(p).strip()]

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not any(has_permission(token) for token in needed):
                if request.path.startswith("/api/"):
                    return json_error("forbidden", "Nicht erlaubt.", status=403)
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def policy_allows(membership: Membership, required: str) -> bool:
    try:
        raw = str(membership.role or "").strip().upper()
        if raw in ROLE_ORDER:
            role = raw
        else:
            role = legacy_role_from_roles(
                [normalize_role_name(raw)], fallback="READONLY"
            )
        required_role = required if required in ROLE_ORDER else "READONLY"
        return ROLE_ORDER.index(role) >= ROLE_ORDER.index(required_role)
    except ValueError:
        return False
