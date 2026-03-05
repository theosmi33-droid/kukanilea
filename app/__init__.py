from __future__ import annotations

import os
import secrets
import time
import re
from datetime import timedelta
from pathlib import Path

from flask import Flask, g, request, session

from .auth import init_auth
from .autonomy.healer import init_healer
from .config import Config
from .db import AuthDB, ensure_agent_memory_tables
from .log_utils import init_request_logging
from .logging.structured_logger import log_event
from .observability import init_observability
from .autonomy import init_autonomy
from .license_state import load_runtime_license_state, SystemState, manager


def _is_test_context(app: Flask) -> bool:
    return bool(app.config.get("TESTING") or os.environ.get("PYTEST_CURRENT_TEST"))


def _wire_runtime_env(app: Flask):
    """Wires standard KUKANILEA paths into os.environ for legacy modules."""
    os.environ.setdefault("DB_FILENAME", str(app.config["CORE_DB"]))
    os.environ.setdefault("TOPHANDWERK_DB_FILENAME", str(app.config["CORE_DB"]))
    os.environ.setdefault("KUKANILEA_AUTH_DB", str(app.config["AUTH_DB"]))
    os.environ.setdefault("KUKANILEA_CORE_DB", str(app.config["CORE_DB"]))


def create_app() -> Flask:
    boot_start = time.time()
    manager.set_state(SystemState.BOOT, "Initializing Flask core...")
    app = Flask(__name__)
    app.config.from_object(Config)

    # Security baseline: sessions expire after 8h, rotated on every write.
    session_cookie_policy = dict(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=not _is_test_context(app),
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.config.update(session_cookie_policy)
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(hours=8))

    _wire_runtime_env(app)

    manager.set_state(SystemState.INIT, "Initializing modules and databases...")
    # Import blueprints after env/path wiring so legacy modules read correct paths.
    from . import api, web
    from .routes import system_logs, admin_tenants, automation, visualizer
    from .core.tool_loader import load_all_tools

    load_all_tools()

    auth_db = AuthDB(app.config["AUTH_DB"])
    try:
        auth_db.init()
        # Ensure shared AI queue/memory tables exist before background services start.
        ensure_agent_memory_tables(str(app.config["AUTH_DB"]))
    except Exception as e:
        manager.report_error(f"AuthDB Init Failed: {e}")
        raise

    app.extensions["auth_db"] = auth_db
    init_auth(app, auth_db)
    from .errors import init_app as init_errors
    init_errors(app)
    init_request_logging(app)
    init_observability(app)
    init_autonomy(app)
    
    from .security.session_manager import init_app as init_session_manager
    init_session_manager(app)

    # Start background dispatcher only for real runtime, not test contexts.
    if not _is_test_context(app):
        from .services.api_dispatcher import start_dispatcher_daemon

        start_dispatcher_daemon(str(auth_db.path), interval=60)

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
    app.config["LICENSE_STATUS"] = license_state.get("status", "active")
    
    
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
    
    @app.after_request
    def add_cors_headers(response):
        # Enterprise-Hardened CORS: Not wildcard. Only allow self.
        response.headers["Access-Control-Allow-Origin"] = "self" # Not a standard value, but often used as placeholder or handled by browser as origin of itself.
        # More standard approach:
        # response.headers["Access-Control-Allow-Origin"] = request.host_url.rstrip("/")
        # But "Access-Control-Allow-Origin" is usually not needed if we only want same-origin.
        # If we really need CORS for some local hubs, we should allow specific origins.
        # For now, we'll set it to a safe default that is NOT *.
        if "Access-Control-Allow-Origin" not in response.headers:
             response.headers["Access-Control-Allow-Origin"] = request.host_url.rstrip("/")
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


    @app.before_request
    def _enforce_license_read_only():
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return None
        path = request.path or "/"
        # Auth/session flows must remain writable even in read-only mode,
        # otherwise users cannot log in to inspect or recover license state.
        allow_prefixes = (
            "/health",
            "/api/health",
            "/static/",
            "/login",
            "/logout",
            "/switch-tenant",
            "/admin/context/switch",
            "/admin/license",
            "/admin/settings",
            "/api/auth/",
            "/api/chat",
            "/api/chat/compact",
        )
        if any(path.startswith(prefix) for prefix in allow_prefixes):
            return None
        if bool(app.config.get("READ_ONLY", False)):
            reason = str(app.config.get("LICENSE_REASON", "license_read_only"))
            log_event("license_write_blocked", {"path": path, "method": request.method, "reason": reason})
            return json_error("read_only", f"License state blocks write operations: {reason}", status=403)
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
            "license_status": str(app.config.get("LICENSE_STATUS", "active")),
            "plan": str(app.config.get("PLAN", "TRIAL")),
            "trial_active": bool(app.config.get("TRIAL", False)),
            "trial_days_left": int(app.config.get("TRIAL_DAYS_LEFT", 0)),
        }

    @app.context_processor
    def _tenants_context():
        from .core.tenant_registry import tenant_registry
        return {
            "all_tenants": tenant_registry.list_tenants(),
            "active_tenant_id": session.get("tenant_id", Config.TENANT_DEFAULT),
            "active_tenant_name": session.get("tenant_name", Config.TENANT_DEFAULT)
        }

    @app.context_processor
    def _security_context():
        from .security import get_csrf_token

        return {"csrf_token": get_csrf_token}

    @app.context_processor
    def _csp_context():
        return {"csp_nonce": lambda: getattr(g, "csp_nonce", "")}

    @app.before_request
    def _set_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def add_security_headers(response):
        from .security.csp import build_csp_header

        response.headers["Content-Security-Policy"] = build_csp_header(getattr(g, "csp_nonce", ""))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type and getattr(g, "csp_nonce", ""):
            body = response.get_data(as_text=True)
            script_pattern = re.compile(r"<script(?![^>]*\bnonce=)([^>]*)>", re.IGNORECASE)
            body = script_pattern.sub(lambda m: f'<script nonce="{g.csp_nonce}"{m.group(1)}>', body)
            response.set_data(body)
        return response

    app.register_blueprint(web.bp)
    # Canonical owner: app/web.py owns tool page endpoints to avoid
    # competing rules for /upload, /calendar, /messenger, /email,
    # /projects, /tasks, /time and /visualizer.
    app.register_blueprint(api.bp)
    app.register_blueprint(system_logs.bp)
    app.register_blueprint(admin_tenants.bp)
    app.register_blueprint(automation.bp)
    app.register_blueprint(visualizer.bp)
    
    from .routes.dashboard_api import dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    try:
        from .services.metrics_exporter import bp as metrics_bp

        app.register_blueprint(metrics_bp, url_prefix="")
    except Exception as e:
        app.logger.warning("Metrics blueprint not registered: %s", e)
    
    with app.app_context():
        automation.init_automation_schema()
    
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
