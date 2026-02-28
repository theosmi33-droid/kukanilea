"""
app/security/session_manager.py
Manages user session lifecycle, timeouts, and invalidation.
"""
from flask import session, current_app, redirect, url_for, request
import time
import functools
import logging

logger = logging.getLogger("kukanilea.session_manager")

SESSION_TIMEOUT_SECONDS = 3600  # 1 hour

def init_app(app):
    @app.before_request
    def check_session_timeout():
        if request.endpoint and request.endpoint.startswith('static'):
            return
            
        if 'user' in session:
            last_active = session.get('last_active')
            now = time.time()
            
            # If last_active is missing, initialize it (emergency fallback)
            if last_active is None:
                session['last_active'] = now
                return
                
            if now - last_active > SESSION_TIMEOUT_SECONDS:
                logger.info(f"Session timeout for user {session['user']}.")
                session.clear()
                # Use request.path instead of full URL to avoid redirect loops with hostnames
                return redirect(url_for('web.login', next=request.path))
            session['last_active'] = now
