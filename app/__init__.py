from __future__ import annotations

import os

from flask import Flask, request

from .auth import init_auth
from .autonomy import init_autonomy
from .config import Config
from .db import AuthDB
from .errors import json_error
from .license import load_runtime_license_state
from .logging import init_request_logging
from .observability import init_observability


def _wire_runtime_env(app: Flask) -> None:
    """Keep legacy core modules pointed to user-data paths."""
    os.environ["KUKANILEA_AUTH_DB"] = str(app.config["AUTH_DB"])
    os.environ["DB_FILENAME"] = str(app.config["CORE_DB"])
    os.environ.setdefault("TOPHANDWERK_DB_FILENAME", str(app.config["CORE_DB"]))


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    _wire_runtime_env(app)

    # Import blueprints after env/path wiring so legacy modules read correct paths.
    from . import api, web

    auth_db = AuthDB(app.config["AUTH_DB"])
    auth_db.init()
    app.extensions["auth_db"] = auth_db
    init_auth(app, auth_db)
    init_request_logging(app)
    init_observability(app)
    init_autonomy(app)

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

    @app.before_request
    def _enforce_read_only():
        if not app.config.get("READ_ONLY"):
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
    def _branding_context():
        return {"branding": Config.get_branding()}

    @app.context_processor
    def _license_context():
        return {
            "read_only": bool(app.config.get("READ_ONLY", False)),
            "license_reason": str(app.config.get("LICENSE_REASON", "")),
            "plan": str(app.config.get("PLAN", "TRIAL")),
            "trial_active": bool(app.config.get("TRIAL", False)),
            "trial_days_left": int(app.config.get("TRIAL_DAYS_LEFT", 0)),
        }

    @app.after_request
    def add_security_headers(response):
        # Strict CSP for Offline-First Compliance (Task 4)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "img-src 'self' data:; "
            "frame-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    if web.db_init is not None:
        try:
            web.db_init()
            if callable(getattr(web.core, "index_warmup", None)):
                web.core.index_warmup(tenant_id=app.config.get("TENANT_DEFAULT", ""))
        except Exception:
            pass
    return app
