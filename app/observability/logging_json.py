from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, request


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


def init_json_logging(app: Flask) -> None:
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
            "request_id": rid,
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
        # Just return the error, don't raise here if we want log_request to catch it via after_request
        # Actually, Flask's after_request DOES run after error handlers.
        # But if we don't return a response, Flask will show a default 500.
        from flask import jsonify

        response = jsonify(
            {
                "error": "Internal Server Error",
                "request_id": getattr(g, "request_id", "-"),
            }
        )
        response.status_code = 500
        return response
