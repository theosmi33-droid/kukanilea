from __future__ import annotations

import os
import secrets
import time
import re
from datetime import timedelta
from pathlib import Path

from flask import Flask, g, request, session

from .auth import init_auth
from .autonomy import init_autonomy
from .config import Config, _is_dev_env
from .db import AuthDB
from .errors import json_error
from .license import load_runtime_license_state
from .log_utils import init_request_logging
from .migrations.ensure_agent_memory import ensure_agent_memory_tables
from .observability import init_observability
from .logging.structured_logger import log_event
from .security.session_policy import resolve_session_cookie_policy


def _wire_runtime_env(app: Flask) -> None:
    """Keep legacy core modules pointed to user-data paths."""
    os.environ["DB_FILENAME"] = str(app.config["CORE_DB"])
    os.environ["TOPHANDWERK_DB_FILENAME"] = str(app.config["CORE_DB"])
    # Keep already-imported legacy logic module in sync with per-app DB path.
    # Without this, tests that create multiple apps can keep writing to a stale DB.
    try:
        import importlib

        core_logic = importlib.import_module("app.core.logic")
        core_logic.DB_PATH = Path(app.config["CORE_DB"])
        core_logic._DB_INITIALIZED = False
    except Exception:
        # Non-fatal: module might not be imported yet in some boot paths.
        pass


from .lifecycle import SystemState, manager


def _is_test_context(app: Flask) -> bool:
    # Pytest sets this environment variable for each test case.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if os.environ.get("KUKANILEA_DISABLE_DAEMONS") == "1":
        return True
    return bool(app.config.get("TESTING"))


def _apply_env_runtime_overrides(app: Flask) -> None:
    """Re-read explicit runtime path env vars for each app instance."""
    env_to_cfg = {
        "KUKANILEA_AUTH_DB": "AUTH_DB",
        "KUKANILEA_CORE_DB": "CORE_DB",
        "KUKANILEA_LICENSE_PATH": "LICENSE_PATH",
        "KUKANILEA_TRIAL_PATH": "TRIAL_PATH",
        "KUKANILEA_RESEARCH_CACHE_PATH": "RESEARCH_CACHE_PATH",
    }
    for env_key, cfg_key in env_to_cfg.items():
        if env_key in os.environ and os.environ.get(env_key):
            app.config[cfg_key] = Path(str(os.environ[env_key]))


def create_app() -> Flask:
    boot_start = time.time()
    manager.set_state(SystemState.BOOT, "Booting application context...")
    app = Flask(__name__)
    app.config.from_object(Config)
    _apply_env_runtime_overrides(app)
    app.secret_key = app.config["SECRET_KEY"]
    explicit_env = str(
        os.environ.get("KUKANILEA_ENV", os.environ.get("FLASK_ENV", ""))
    ).strip().lower()
    session_cookie_policy = resolve_session_cookie_policy(
        explicit_env=explicit_env,
        configured_secure=app.config.get("SESSION_COOKIE_SECURE"),
    )
    app.config.update(session_cookie_policy)
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(hours=8))

    _wire_runtime_env(app)

    manager.set_state(SystemState.INIT, "Initializing modules and databases...")
    # Import blueprints after env/path wiring so legacy modules read correct paths.
    from . import api, web
    from .routes import system_logs, admin_tenants, automation, visualizer, email
    from .core.tool_loader import load_all_tools
    from .core.event_flows import init_event_flows

    load_all_tools(app)
    init_event_flows()

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
    init_request_logging(app)
    init_observability(app)
    init_autonomy(app)
    
    from .security.session_manager import init_app as init_session_manager
    init_session_manager(app)

    # Start background dispatcher only for real runtime, not test contexts.
    if not _is_test_context(app):
        from .services.api_dispatcher import start_dispatcher_daemon
        from .modules.dashboard.briefing import start_briefing_scheduler

        start_dispatcher_daemon(str(auth_db.path), interval=60)
        start_briefing_scheduler()

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
    def _enforce_confirm_gates():
        # PKG-GRD-02: Global Confirm-Gate & Injection Enforcement
        path = request.path or "/"
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        
        from .security.gates import CRITICAL_CONFIRM_GATE_BY_ROUTE, scan_payload_for_injection, confirm_gate
        from .mia_audit import emit_mia_event, MIA_EVENT_CONFIRM_REQUESTED, MIA_EVENT_CONFIRM_DENIED, MIA_EVENT_CONFIRM_GRANTED

        policy = CRITICAL_CONFIRM_GATE_BY_ROUTE.get(path)
        if not policy:
            # Generic injection scan for all mutating requests if needed? 
            # For now, stick to policy-driven to avoid false positives.
            return None

        # 1. Get Payload (JSON or Form)
        payload = request.get_json(silent=True) or request.form.to_dict()
        
        # 2. Injection Scan
        finding = scan_payload_for_injection(payload, policy.fields)
        if finding:
            log_event("security_injection_blocked", {"path": path, "field": finding.field})
            return json_error("injection_blocked", f"Potential injection detected in field: {finding.field}", status=400)
            
        # 3. Confirm Check
        if not policy.required:
            return None
            
        tenant_id = session.get("tenant_id") or app.config.get("TENANT_DEFAULT") or "KUKANILEA"
        actor = session.get("user") or "system"
        flow_ref = f"gate-{path.replace('/', '-')}"
        
        confirm_val = payload.get("confirm")
        if not confirm_gate(confirm_val):
            emit_mia_event(
                event_type=MIA_EVENT_CONFIRM_DENIED,
                entity_type="confirm_gate",
                entity_ref=flow_ref,
                tenant_id=tenant_id,
                payload={"actor": actor, "reason": "token_missing_or_invalid", "path": path}
            )
            return json_error("confirm_required", "Explicit confirmation required for this action.", status=409)

        # Log Grant (Success)
        emit_mia_event(
            event_type=MIA_EVENT_CONFIRM_GRANTED,
            entity_type="confirm_gate",
            entity_ref=flow_ref,
            tenant_id=tenant_id,
            payload={"actor": actor, "path": path}
        )
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
            "/api/research/",
            "/api/news/",
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
    app.register_blueprint(email.bp)
    
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
