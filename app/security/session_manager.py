"""
app/security/session_manager.py
Manages user session lifecycle, timeouts, and invalidation.
"""
from flask import session, current_app, redirect, url_for, request
import time
import logging
import secrets

logger = logging.getLogger("kukanilea.session_manager")

SESSION_TIMEOUT_SECONDS = 3600  # 1 hour
SESSION_ABSOLUTE_TIMEOUT_SECONDS = 8 * 3600
SESSION_ROTATE_SECONDS = 15 * 60

def init_app(app):
    @app.before_request
    def check_session_timeout():
        if request.endpoint and request.endpoint.startswith('static'):
            return

        if 'user' in session:
            last_active = session.get('last_active')
            issued_at = session.get('session_issued_at')
            rotation_at = session.get('session_rotation_at')
            now = time.time()

            # If last_active is missing, initialize it (emergency fallback)
            if last_active is None:
                session['last_active'] = now
                session['session_issued_at'] = now
                session['session_rotation_at'] = now
                return

            if issued_at is None:
                session['session_issued_at'] = now
                issued_at = now

            if now - float(issued_at) > SESSION_ABSOLUTE_TIMEOUT_SECONDS:
                logger.info("Absolute session expiry for user %s.", session.get('user'))
                session.clear()
                return redirect(url_for('web.login', next=request.path))

            if now - last_active > SESSION_TIMEOUT_SECONDS:
                logger.info("Session timeout for user %s.", session.get('user'))
                session.clear()
                # Use request.path instead of full URL to avoid redirect loops with hostnames
                return redirect(url_for('web.login', next=request.path))

            if rotation_at is None or (now - float(rotation_at) > SESSION_ROTATE_SECONDS):
                session['session_sid'] = secrets.token_urlsafe(24)
                session['session_rotation_at'] = now
            session['last_active'] = now
