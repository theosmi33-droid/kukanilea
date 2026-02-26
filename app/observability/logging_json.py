from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "route": getattr(record, "route", "-"),
            "status_code": getattr(record, "status_code", 0),
            "duration_ms": getattr(record, "duration_ms", 0),
        }
        if hasattr(record, "tenant_id") and record.tenant_id != "-":
            log_data["tenant_hash"] = hashlib.sha256(
                str(record.tenant_id).encode()
            ).hexdigest()[:12]
        if record.exc_info:
            log_data["error_class"] = record.exc_info[0].__name__
        elif hasattr(record, "error_class"):
            log_data["error_class"] = record.error_class

        return json.dumps(log_data)


def init_json_logging(app) -> None:
    from flask import g, request

    log_dir = Path(app.config.get("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.jsonl"

    logger = logging.getLogger("kukanilea_json")
    logger.setLevel(logging.INFO)

    # In tests, log_file might change between runs but logger persists.
    # Check if existing handler points to the same file.
    needs_new_handler = True
    if logger.handlers:
        for h in logger.handlers:
            if isinstance(h, RotatingFileHandler) and h.baseFilename == str(
                log_file.absolute()
            ):
                needs_new_handler = False
                break

    if needs_new_handler:
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()

        # Strict Rotation: 50MB per file, max 3 backups (Total 200MB max)
        handler = RotatingFileHandler(
            log_file, maxBytes=50 * 1024 * 1024, backupCount=3
        )
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    @app.before_request
    def start_timer():
        g.start_time = time.time()
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def log_request(response):
        if request.path.startswith("/static"):
            return response

        duration_ms = int((time.time() - getattr(g, "start_time", time.time())) * 1000)
        rid = getattr(g, "request_id", "-")

        tenant_id = app.config.get("TENANT_DEFAULT", "-")

        log_extra = {
            "route": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "tenant_id": tenant_id,
            "error_class": getattr(g, "error_class", "-"),
        }

        logger.info(f"{request.method} {request.path}", extra=log_extra)

        response.headers["X-Request-Id"] = rid
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        g.error_class = e.__class__.__name__
        from flask import jsonify, render_template_string

        request_id = getattr(g, "request_id", "-")

        # Decision: JSON or HTML?
        is_api = request.path.startswith(
            "/api"
        ) or "application/json" in request.headers.get("Accept", "")

        if is_api:
            response = jsonify(
                {
                    "ok": False,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "Ein interner Fehler ist aufgetreten.",
                        "details": {"request_id": request_id},
                    },
                }
            )
            response.status_code = 500
            return response

        # HTML Error Page for Browser
        error_html = f"""
        <!doctype html>
        <html lang="de">
        <head>
            <meta charset="utf-8">
            <title>Fehler - KUKANILEA</title>
            <style>
                body {{ font-family: sans-serif; background: #060b16; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                .container {{ text-align: center; border: 1px solid rgba(255,255,255,0.1); padding: 40px; border-radius: 24px; background: rgba(30,41,59,0.4); backdrop-filter: blur(10px); max-width: 500px; }}
                h1 {{ color: #38bdf8; margin-top: 0; }}
                .rid {{ font-family: monospace; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 12px; margin: 24px 0; border: 1px solid rgba(255,255,255,0.05); color: #94a3b8; }}
                a {{ color: #38bdf8; text-decoration: none; font-weight: bold; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Ups! Etwas lief schief.</h1>
                <p>Ein interner Fehler ist aufgetreten. Bitte wenden Sie sich an den Support und geben Sie die folgende ID an:</p>
                <div class="rid">{request_id}</div>
                <a href="/">Zurück zum Dashboard</a>
            </div>
        </body>
        </html>
        """
        return render_template_string(error_html), 500

    @app.errorhandler(404)
    def handle_404(e):
        from flask import jsonify, render_template_string

        request_id = getattr(g, "request_id", "-")
        is_api = request.path.startswith(
            "/api"
        ) or "application/json" in request.headers.get("Accept", "")

        if is_api:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Die angeforderte Ressource wurde nicht gefunden.",
                            "details": {"request_id": request_id},
                        },
                    }
                ),
                404,
            )

        error_html = """
        <!doctype html>
        <html lang="de">
        <head><meta charset="utf-8"><title>404 - KUKANILEA</title>
        <style>body{font-family:sans-serif;background:#060b16;color:white;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .container{text-align:center;border:1px solid rgba(255,255,255,0.1);padding:40px;border-radius:24px;background:rgba(30,41,59,0.4);} h1{color:#38bdf8;}</style>
        </head><body><div class="container"><h1>404 - Nicht gefunden</h1><p>Diese Seite existiert nicht.</p><a href="/" style="color:#38bdf8;text-decoration:none;">Zurück zum Dashboard</a></div></body></html>
        """
        return render_template_string(error_html), 404

    @app.errorhandler(403)
    def handle_403(e):
        from flask import jsonify, render_template_string

        request_id = getattr(g, "request_id", "-")
        is_api = request.path.startswith(
            "/api"
        ) or "application/json" in request.headers.get("Accept", "")

        if is_api:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": {
                            "code": "FORBIDDEN",
                            "message": "Zugriff verweigert.",
                            "details": {"request_id": request_id},
                        },
                    }
                ),
                403,
            )

        error_html = """
        <!doctype html>
        <html lang="de">
        <head><meta charset="utf-8"><title>403 - KUKANILEA</title>
        <style>body{font-family:sans-serif;background:#060b16;color:white;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;} .container{text-align:center;border:1px solid rgba(255,255,255,0.1);padding:40px;border-radius:24px;background:rgba(30,41,59,0.4);} h1{color:#ef4444;}</style>
        </head><body><div class="container"><h1>403 - Zugriff verweigert</h1><p>Sie haben keine Berechtigung für diese Aktion.</p><a href="/" style="color:#38bdf8;text-decoration:none;">Zurück zum Dashboard</a></div></body></html>
        """
        return render_template_string(error_html), 403
