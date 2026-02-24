from __future__ import annotations

import logging as py_logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template_string,
    request,
    session as flask_session,
    url_for,
)
from werkzeug.exceptions import HTTPException

from .ai import init_ai
from .auth import init_auth
from .autonomy.healer import init_healer
from .bootstrap import is_localhost_addr, needs_bootstrap
from .config import Config
from .db import AuthDB
from .errors import handle_error
from .hardware_detection import init_hardware_detection
from .license import load_runtime_license_state
from .logging import init_request_logging
from .observability import setup_observability
from .observability.otel import setup_otel
from .tenant.context import ensure_tenant_config, load_tenant_context

_SESSION_TIMEOUT_PUBLIC_PATHS = {
    "/login",
    "/logout",
    "/register",
    "/verify-email",
    "/forgot-password",
    "/reset-password",
    "/bootstrap",
    "/license",
    "/health",
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
    "/api/ping",
    "/app.webmanifest",
    "/sw.js",
    "/auth/google/start",
    "/auth/google/callback",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_session_iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _parse_session_iso(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    token = raw
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(token)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _session_idle_minutes(app: Flask, raw: object) -> int:
    default_val = int(app.config.get("SESSION_IDLE_TIMEOUT_DEFAULT_MINUTES", 60) or 60)
    min_val = int(app.config.get("SESSION_IDLE_TIMEOUT_MIN_MINUTES", 15) or 15)
    max_val = int(app.config.get("SESSION_IDLE_TIMEOUT_MAX_MINUTES", 480) or 480)
    if min_val > max_val:
        min_val, max_val = max_val, min_val
    try:
        value = int(raw)
    except Exception:
        value = default_val
    return max(min_val, min(max_val, value))


def _session_timeout_response(reason: str):
    if request.path.startswith("/api/"):
        return json_error("session_timeout", f"Sitzung beendet ({reason}).", status=401)
    return redirect(url_for("web.login", next=request.path))


def _wire_runtime_env(app: Flask) -> None:
    """Keep legacy core modules pointed to user-data paths."""
    os.environ["KUKANILEA_AUTH_DB"] = str(app.config["AUTH_DB"])
    os.environ["DB_FILENAME"] = str(app.config["CORE_DB"])
    os.environ.setdefault("TOPHANDWERK_DB_FILENAME", str(app.config["CORE_DB"]))


def _active_tab_from_path(path: str) -> str:
    token = str(path or "").strip().lower()
    if token.startswith("/tasks"):
        return "tasks"
    if token.startswith("/time"):
        return "time"
    if token.startswith("/assistant"):
        return "assistant"
    if token.startswith("/chat"):
        return "chat"
    if token.startswith("/postfach") or token.startswith("/mail"):
        return "postfach"
    if token.startswith("/crm"):
        return "crm"
    if token.startswith("/leads"):
        return "leads"
    if token.startswith("/knowledge"):
        return "knowledge"
    if token.startswith("/conversations"):
        return "conversations"
    if token.startswith("/workflows"):
        return "workflows"
    if token.startswith("/automation"):
        return "automation"
    if token.startswith("/autonomy"):
        return "autonomy"
    if token.startswith("/insights"):
        return "insights"
    if token.startswith("/license"):
        return "license"
    if token.startswith("/settings") or token.startswith("/dev/"):
        return "settings"
    return "upload"


def _resource_dir() -> Path:
    """Resolve template/static root for source and frozen desktop bundles."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(str(meipass)).resolve()
    return Path(__file__).resolve().parent.parent


def create_app(system_settings: dict | None = None) -> Flask:
    # 0. Initialisierung mit Hardware-Limits falls übergeben
    if system_settings:
        # Hier könnten globale Limits in app.config oder os.environ geschrieben werden
        import os
        os.environ["KUKANILEA_ADAPTIVE_WORKERS"] = str(system_settings.get("worker_threads", 2))
        os.environ["KUKANILEA_ADAPTIVE_DB_CACHE"] = str(system_settings.get("db_cache_size_mb", 128))
        os.environ["KUKANILEA_ADAPTIVE_AI_MODEL"] = str(system_settings.get("ai_model", "llama3.2:3b"))

    resources = _resource_dir()
    app = Flask(
        __name__,
        template_folder=str(resources / "templates"),
        static_folder=str(resources / "static"),
    )
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    _wire_runtime_env(app)

    # Import blueprints after env/path wiring so legacy modules read correct paths.
    from . import ai_chat, api, web
    from .ui.onboarding_wizard import onboarding_bp
    
    app.register_blueprint(onboarding_bp)

    @app.before_request
    def _enforce_activation():
        from .core.license_manager import license_manager
        if request.endpoint and "onboarding" in request.endpoint:
            return None
        if request.path.startswith("/static/"):
            return None
        if not license_manager.is_valid():
            if request.path.startswith("/api/"):
                return json_error("license_invalid", "System nicht aktiviert.", status=402)
            return redirect(url_for("onboarding.activate"))
        return None

    @app.context_processor
    def _inject_license_status():
        from .core.license_manager import license_manager
        return {"license_valid": license_manager.is_valid()}

    auth_db = AuthDB(app.config["AUTH_DB"])
    auth_db.init()
    app.extensions["auth_db"] = auth_db
    tenant_db_path = Path(
        str(getattr(getattr(web, "core", None), "DB_PATH", app.config["CORE_DB"]))
    )
    app.config["TENANT_CONFIG_DB_PATH"] = tenant_db_path
    tenant_ctx = ensure_tenant_config(
        db_path=tenant_db_path,
        license_path=app.config["LICENSE_PATH"],
        fallback_tenant_id=str(app.config.get("TENANT_DEFAULT", "KUKANILEA")),
        fallback_tenant_name=str(app.config.get("TENANT_NAME", "KUKANILEA")),
    )
    app.config["TENANT_DEFAULT"] = tenant_ctx.tenant_id
    app.config["TENANT_NAME"] = tenant_ctx.tenant_name
    init_auth(app, auth_db)
    init_request_logging(app)
    
    setup_observability(app)
    setup_otel(app)
    init_healer(app)

    license_state = load_runtime_license_state(
        license_path=app.config["LICENSE_PATH"],
        trial_path=app.config["TRIAL_PATH"],
        trial_days=int(app.config.get("TRIAL_DAYS", 14)),
        cache_path=app.config.get("LICENSE_CACHE_PATH"),
        validate_url=str(app.config.get("LICENSE_VALIDATE_URL", "")),
        validate_timeout_seconds=int(
            app.config.get("LICENSE_VALIDATE_TIMEOUT_SECONDS", 10)
        ),
        validate_interval_days=int(
            app.config.get("LICENSE_VALIDATE_INTERVAL_DAYS", 30)
        ),
        grace_days=int(app.config.get("LICENSE_GRACE_DAYS", 30)),
    )
    app.config["PLAN"] = license_state["plan"]
    app.config["TRIAL"] = license_state["trial"]
    app.config["TRIAL_DAYS_LEFT"] = license_state["trial_days_left"]
    app.config["READ_ONLY"] = license_state["read_only"]
    app.config["LICENSE_REASON"] = license_state["reason"]
    app.config["LICENSE_GRACE_ACTIVE"] = bool(license_state.get("grace_active", False))
    app.config["LICENSE_GRACE_DAYS_LEFT"] = int(
        license_state.get("grace_days_left", 0) or 0
    )
    app.config["LICENSE_VALIDATED_ONLINE"] = bool(
        license_state.get("validated_online", False)
    )
    app.config["LICENSE_LAST_VALIDATED"] = str(license_state.get("last_validated", ""))

    @app.before_request
    def _enforce_bootstrap():
        if app.config.get("TESTING"):
            return None
        if not needs_bootstrap(auth_db):
            return None
        path = (request.path or "").rstrip("/") or "/"
        if not is_localhost_addr(request.remote_addr):
            if path.startswith("/api/"):
                return json_error(
                    "bootstrap_localhost_only",
                    "Bootstrap nur auf localhost erlaubt.",
                    status=403,
                )
            abort(403)
        if path.startswith("/static/") or path == "/bootstrap":
            return None
        return redirect(url_for("web.bootstrap"))

    @app.before_request
    def _set_tenant_context():
        if bool(app.config.get("TESTING", False)) and not bool(
            app.config.get("TENANT_FIXED_TEST_ENFORCE", False)
        ):
            return None
        path = (request.path or "").rstrip("/") or "/"
        if path.startswith("/static/"):
            return None
        if path in {
            "/login",
            "/logout",
            "/bootstrap",
            "/license",
            "/health",
            "/api/health",
            "/api/health/live",
            "/api/health/ready",
            "/api/ping",
            "/app.webmanifest",
            "/sw.js",
        }:
            return None
        ctx = load_tenant_context(Path(app.config["TENANT_CONFIG_DB_PATH"]))
        if ctx is None:
            if path.startswith("/api/"):
                return json_error(
                    "tenant_not_configured",
                    "Tenant nicht konfiguriert.",
                    status=403,
                )
            abort(403)
        g.tenant_ctx = ctx
        g.tenant_id = ctx.tenant_id
        # Override any client/session tenant to enforce fixed installation tenant.
        if flask_session.get("tenant_id") != ctx.tenant_id:
            flask_session["tenant_id"] = ctx.tenant_id
        return None

    @app.before_request
    def _enforce_session_timeouts():
        path = (request.path or "").rstrip("/") or "/"
        if path.startswith("/static/") or path in _SESSION_TIMEOUT_PUBLIC_PATHS:
            return None
        if not flask_session.get("user"):
            return None

        now = _utcnow()
        flask_session.permanent = True

        created_at = _parse_session_iso(flask_session.get("session_created_at"))
        if created_at is None:
            flask_session["session_created_at"] = _to_session_iso(now)
            created_at = now

        absolute_cap = app.permanent_session_lifetime
        if not isinstance(absolute_cap, timedelta):
            absolute_cap = timedelta(hours=8)
        if now - created_at > absolute_cap:
            flask_session.clear()
            return _session_timeout_response("maximale Sitzungsdauer erreicht")

        last_activity = _parse_session_iso(flask_session.get("last_activity"))
        if last_activity is None:
            flask_session["last_activity"] = _to_session_iso(now)
            return None

        idle_minutes = _session_idle_minutes(app, flask_session.get("idle_timeout_minutes"))
        try:
            stored_idle = int(flask_session.get("idle_timeout_minutes", idle_minutes))
        except Exception:
            stored_idle = None
        if stored_idle != idle_minutes:
            flask_session["idle_timeout_minutes"] = idle_minutes

        if (now - last_activity).total_seconds() > float(idle_minutes * 60):
            flask_session.clear()
            return _session_timeout_response("Inaktivität")

        touch_seconds = int(app.config.get("SESSION_IDLE_TOUCH_SECONDS", 60) or 60)
        if touch_seconds < 1:
            touch_seconds = 1
        if (now - last_activity).total_seconds() >= touch_seconds:
            flask_session["last_activity"] = _to_session_iso(now)
        return None

    @app.before_request
    def _enforce_read_only():
        if not app.config.get("READ_ONLY"):
            return None
        path = (request.path or "").rstrip("/") or "/"
        # License activation must remain possible when instance is read-only.
        if path in {"/license", "/bootstrap"}:
            return None
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            return json_error(
                "read_only",
                "Instanz ist schreibgeschuetzt (Lizenz/Trial).",
                status=403,
                details={
                    "reason": app.config.get("LICENSE_REASON", "read_only"),
                    "plan": app.config.get("PLAN", "TRIAL"),
                },
            )
        return None

    @app.context_processor
    def _license_context():
        return {
            "read_only": bool(app.config.get("READ_ONLY", False)),
            "license_reason": str(app.config.get("LICENSE_REASON", "")),
            "plan": str(app.config.get("PLAN", "TRIAL")),
            "trial_active": bool(app.config.get("TRIAL", False)),
            "trial_days_left": int(app.config.get("TRIAL_DAYS_LEFT", 0)),
            "license_grace_active": bool(app.config.get("LICENSE_GRACE_ACTIVE", False)),
            "license_grace_days_left": int(
                app.config.get("LICENSE_GRACE_DAYS_LEFT", 0)
            ),
            "license_validated_online": bool(
                app.config.get("LICENSE_VALIDATED_ONLINE", False)
            ),
            "license_last_validated": str(app.config.get("LICENSE_LAST_VALIDATED", "")),
        }

    logger = py_logging.getLogger("kukanilea")

    from .errors import handle_error
    app.errorhandler(Exception)(handle_error)

    @app.after_request
    def _set_security_headers(response):
        csp = "; ".join(
            [
                "default-src 'self'",
                "font-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                "script-src 'self' 'unsafe-inline'",
                "img-src 'self' data:",
                "connect-src 'self' http://127.0.0.1:11434",  # Nur Localhost (Ollama)
                "base-uri 'self'",
                "frame-ancestors 'none'",
                "object-src 'none'",
            ]
        )
        response.headers["Content-Security-Policy"] = csp
        return response

    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(ai_chat.bp)
    if web.db_init is not None:
        try:
            web.db_init()
            if callable(getattr(web.core, "index_warmup", None)):
                web.core.index_warmup(tenant_id=app.config.get("TENANT_DEFAULT", ""))
        except Exception:
            pass
    try:
        init_ai(app)
    except Exception:
        pass
    try:
        if not bool(app.config.get("TESTING", False)):
            from .ai.provisioning import start_first_install_bootstrap_background

            start_first_install_bootstrap_background(app.config)
    except Exception:
        pass
    try:
        should_start_reloader_proc = os.environ.get(
            "WERKZEUG_RUN_MAIN"
        ) == "true" or not bool(app.debug)
        is_pytest = "PYTEST_CURRENT_TEST" in os.environ
        if (
            bool(app.config.get("STARTUP_MAINTENANCE_ENABLED", True))
            and not bool(app.config.get("TESTING", False))
            and not is_pytest
            and should_start_reloader_proc
        ):
            from .startup_maintenance import start_startup_maintenance_background

            start_startup_maintenance_background(app.config)
    except Exception:
        pass
    try:
        cron_enabled = bool(app.config.get("AUTOMATION_CRON_ENABLED", True))
        should_start_reloader_proc = os.environ.get(
            "WERKZEUG_RUN_MAIN"
        ) == "true" or not bool(app.debug)
        is_pytest = "PYTEST_CURRENT_TEST" in os.environ
        if (
            cron_enabled
            and not bool(app.config.get("TESTING", False))
            and not is_pytest
            and should_start_reloader_proc
        ):
            from .automation import start_cron_checker

            start_cron_checker(
                db_path=app.config["CORE_DB"],
                interval_seconds=int(
                    app.config.get("AUTOMATION_CRON_INTERVAL_SECONDS", 60)
                ),
            )
    except Exception:
        pass
    return app
