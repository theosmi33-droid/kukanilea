from __future__ import annotations

import functools
import hashlib
from typing import Optional

from flask import abort, g, jsonify, redirect, request, session, url_for

from .db import AuthDB, Membership


ROLE_ORDER = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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
                return jsonify(ok=False, error="unauthorized", code="unauthorized"), 401
            return redirect(url_for("web.login", next=request.path))
        return func(*args, **kwargs)

    return wrapper


def require_role(min_role: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if ROLE_ORDER.index(current_role()) < ROLE_ORDER.index(min_role):
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def policy_allows(membership: Membership, required: str) -> bool:
    try:
        return ROLE_ORDER.index(membership.role) >= ROLE_ORDER.index(required)
    except ValueError:
        return False
