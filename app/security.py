from __future__ import annotations

import functools
import secrets

from flask import abort, request, session


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def set_security_headers(response):
    """Set security headers."""
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "font-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "frame-src 'self' blob: data:;"
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


def csrf_protected(fn):
    """
    Decorator to protect routes against CSRF.
    Checks X-CSRF-Token header or csrf_token in form data.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return fn(*args, **kwargs)

        token = session.get("csrf_token")
        if not token:
            abort(403, description="CSRF token missing in session.")

        provided = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if not provided or provided != token:
            abort(403, description="CSRF token mismatch or missing.")

        return fn(*args, **kwargs)

    return wrapper
