"""
app/security/session_manager.py
Manages user session lifecycle, timeouts, and invalidation.
"""

from __future__ import annotations

import logging
import secrets
import time

from flask import current_app, redirect, request, session, url_for

logger = logging.getLogger("kukanilea.session_manager")
ROTATE_INTERVAL_SECONDS = 15 * 60


def _logout_to_login():
    session.clear()
    return redirect(url_for("web.login", next=request.path))


def init_app(app):
    @app.before_request
    def check_session_timeout():
        if request.endpoint and request.endpoint.startswith("static"):
            return None

        if "user" not in session:
            return None

        now = time.time()
        idle_timeout = int(current_app.config.get("SESSION_IDLE_TIMEOUT_SECONDS", 3600))
        absolute_timeout = int(current_app.config.get("SESSION_ABSOLUTE_TIMEOUT_SECONDS", 8 * 3600))

        issued_at = float(session.get("issued_at") or now)
        last_active = float(session.get("last_active") or now)

        if now - issued_at > absolute_timeout:
            logger.info("Session absolute timeout for user %s.", session.get("user"))
            return _logout_to_login()

        if now - last_active > idle_timeout:
            logger.info("Session idle timeout for user %s.", session.get("user"))
            return _logout_to_login()

        rotated_at = float(session.get("session_rotated_at") or issued_at)
        if now - rotated_at > ROTATE_INTERVAL_SECONDS:
            session["session_nonce"] = secrets.token_urlsafe(24)
            session["session_rotated_at"] = now

        session["last_active"] = now
        return None
