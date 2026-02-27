from __future__ import annotations

import os
import time

from flask import Flask, request

from .auth import init_auth
from .autonomy import init_autonomy
from .config import Config
from .db import AuthDB
from .errors import json_error
from .license import load_runtime_license_state
from .log_utils import init_request_logging
from .observability import init_observability


def _wire_runtime_env(app: Flask) -> None:
    """Keep legacy core modules pointed to user-data paths."""
    os.environ["KUKANILEA_AUTH_DB"] = str(app.config["AUTH_DB"])
    os.environ["DB_FILENAME"] = str(app.config["CORE_DB"])
    os.environ.setdefault("TOPHANDWERK_DB_FILENAME", str(app.config["CORE_DB"]))


from .lifecycle import SystemState, manager


def create_app() -> Flask:
    boot_start = time.time()
    manager.set_state(SystemState.BOOT, "Booting application context...")
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    _wire_runtime_env(app)

    manager.set_state(SystemState.INIT, "Initializing modules and databases...")
    # Import blueprints after env/path wiring so legacy modules read correct paths.
    from . import api, web
    from .routes import system_logs

    auth_db = AuthDB(app.config["AUTH_DB"])
    try:
        auth_db.init()
    except Exception as e:
        manager.report_error(f"AuthDB Init Failed: {e}")
        raise

    app.extensions["auth_db"] = auth_db
    init_auth(app, auth_db)
    init_request_logging(app)
    init_observability(app)
    init_autonomy(app)
    
    from .security.session_manager import init_app as init_session_manager
    init_session_manager(app)

    manager.set_state(SystemState.INIT, "Loading license state...")
    license_state = load_runtime_license_state(
        license_path=app.config["LICENSE_PATH"],
        trial_path=app.config["TRIAL_PATH"],
        trial_days=int(app.config.get("TRIAL_DAYS", 14)),
    )
    app.config["PLAN"] = license_state["plan"]
    app.config["TRIAL"] = license_state["trial"]
    app.config["TRIAL_DAYS_LEFT"] = license_state["trial_days_left"]
    app.config["READ_ONLY"] = license_state["read_only"]
    app.config["LICENSE_REASON"] = license_state["reason"]
    
    from flask import g
    
    @app.before_request
    def start_timer():
        g.start_time = time.time()
        
    @app.after_request
    def log_render_time(response):
        if hasattr(g, 'start_time'):
            elapsed = (time.time() - g.start_time) * 1000
            response.headers["X-Render-Time"] = f"{elapsed:.2f}ms"
            if elapsed > 100 and request.endpoint and not request.endpoint.startswith('static'):
                app.logger.warning(f"⚠️ UI Render SLA missed: {request.path} took {elapsed:.2f}ms")
        return response
    
    # ... Context Processors and Headers ...

    @app.before_request
    def _check_system_ready():
        # Prevent requests if system is in ERROR state, 
        # but allow health checks and static files
        p = request.path or "/"
        if p.startswith("/static/") or p in ["/health", "/api/health"]:
            return None
        
        if manager.state == SystemState.ERROR:
            return json_error("system_error", f"System is in ERROR state: {manager.details}", status=503)
        return None

    @app.context_processor
    def _lifecycle_context():
        return {"system_state": manager.state.value, "system_details": manager.details}

    @app.context_processor
    def _branding_context():
        return {"branding": Config.get_branding()}

    @app.context_processor
    def _license_context():
        from .auth import current_role

        is_dev = current_role() == "DEV"
        read_only = bool(app.config.get("READ_ONLY", False))
        return {
            "read_only": read_only and not is_dev,
            "license_reason": str(app.config.get("LICENSE_REASON", "")),
            "plan": str(app.config.get("PLAN", "TRIAL")),
            "trial_active": bool(app.config.get("TRIAL", False)),
            "trial_days_left": int(app.config.get("TRIAL_DAYS_LEFT", 0)),
        }

    @app.context_processor
    def _security_context():
        from .security import get_csrf_token

        return {"csrf_token": get_csrf_token}

    @app.after_request
    def add_security_headers(response):
        # Strict CSP for Offline-First Compliance (Task 4)
        # Permissive for local previews (PDF/Images)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "img-src 'self' data: blob:; "
            "frame-src 'self' blob: data:; "
            "object-src 'self' blob: data:;"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(system_logs.bp)
    
    manager.set_state(SystemState.INIT, "Warming up database and indexes...")
    if web.db_init is not None:
        try:
            web.db_init()
            if callable(getattr(web.core, "index_warmup", None)):
                web.core.index_warmup(tenant_id=app.config.get("TENANT_DEFAULT", ""))
        except Exception as e:
            manager.report_error(f"Database Warmup Failed: {e}")
            # Non-critical but logged
    
    boot_time = time.time() - boot_start
    manager.set_state(SystemState.READY, f"System is active. (Boot time: {boot_time:.2f}s)")
    return app
