from __future__ import annotations

import functools
import hashlib
import hmac
import secrets
from typing import Optional

from flask import abort, g, redirect, request, session, url_for

from .db import AuthDB, Membership
from .errors import json_error

ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


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


def logout_user() -> None:
    session.clear()


def current_user() -> Optional[str]:
    return session.get("user")


def current_role() -> str:
    return session.get("role") or "READONLY"


def current_tenant() -> str:
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
