from __future__ import annotations

from flask import Flask

from .config import Config
from .db import AuthDB
from .auth import init_auth
from . import web, api
from .logging import init_request_logging


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config["SECRET_KEY"]
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    auth_db = AuthDB(app.config["AUTH_DB"])
    auth_db.init()
    app.extensions["auth_db"] = auth_db
    init_auth(app, auth_db)
    init_request_logging(app)

    app.register_blueprint(web.bp)
    app.register_blueprint(api.bp)
    if web.db_init is not None:
        try:
            web.db_init()
        except Exception:
            pass
    return app
