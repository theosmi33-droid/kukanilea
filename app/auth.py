from __future__ import annotations

import functools
import hashlib
import time
from typing import Iterable, Optional

from flask import abort, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import AuthDB, Membership
from .errors import json_error

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


def hash_password(password: str) -> str:
    # Use a slow, salted KDF for new credentials.
    return generate_password_hash(password, method="scrypt")


def _is_legacy_sha256_hash(password_hash: str) -> bool:
    if len(password_hash or "") != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in password_hash.lower())


def verify_password(password_hash: str, password: str) -> tuple[bool, bool]:
    """
    Returns (valid, needs_rehash).
    needs_rehash=True when a legacy SHA-256 hash was accepted.
    """
    stored = (password_hash or "").strip()
    if not stored:
        return False, False

    if _is_legacy_sha256_hash(stored):
        incoming = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return incoming == stored, True

    try:
        return check_password_hash(stored, password), False
    except Exception:
        return False, False


def init_auth(app, db: AuthDB) -> None:
    app.before_request(lambda: _load_user(db))


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


def login_user(username: str, role: str, tenant_id: str) -> None:
    session["user"] = username
    session["role"] = role
    session["tenant_id"] = tenant_id
    session["last_active"] = time.time()


def logout_user() -> None:
    session.clear()


def current_user() -> Optional[str]:
    return session.get("user")


def current_role() -> str:
    role = session.get("role")
    if role in ROLE_ORDER:
        return role
    return "READONLY"


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


def _normalize_role_threshold(min_role: str) -> str:
    return min_role if min_role in ROLE_ORDER else "READONLY"


def _normalize_role_set(allowed_roles: Iterable[str]) -> set[str]:
    roles = {role for role in allowed_roles if role in ROLE_ORDER}
    return roles or {"READONLY"}


def require_role(min_role: str | Iterable[str]):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                role = current_role()
                if role not in ROLE_ORDER:
                    role = "READONLY"
                allowed_roles: Optional[set[str]] = None
                required_threshold = "READONLY"

                if isinstance(min_role, str):
                    required_threshold = _normalize_role_threshold(min_role)
                else:
                    allowed_roles = _normalize_role_set(min_role)

                denied = False
                if allowed_roles is not None:
                    denied = role not in allowed_roles
                else:
                    denied = ROLE_ORDER.index(role) < ROLE_ORDER.index(required_threshold)

                if denied:
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
