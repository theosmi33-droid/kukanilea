from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

from flask import Flask, g, request

from app.config import get_data_dir
from app.log_utils import PIISafeFormatter


class JSONFormatter(PIISafeFormatter):
    """
    Structured JSON Formatter for KUKANILEA.
    Ensures machine-readability while maintaining PII-safety.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Redact message using parent logic first
        redacted_msg = super().format(record)

        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redacted_msg,
            "request_id": getattr(record, "rid", "-"),
            "method": getattr(record, "method", "-"),
            "route": getattr(record, "route", "-"),
            "status_code": getattr(record, "status_code", 0),
            "duration_ms": getattr(record, "duration_ms", 0),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "tenant_id") and record.tenant_id:
            log_entry["tenant_hash"] = hashlib.sha256(str(record.tenant_id).encode()).hexdigest()[:12]

        if record.exc_info:
            log_entry["error_class"] = record.exc_info[0].__name__
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_observability(app: Flask | None = None):
    """Sets up lightweight local observability."""
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("kukanilea")
    logger.setLevel(logging.INFO)

    # File Handler for JSON logs with rotation
    log_file = log_dir / "app.jsonl"
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(JSONFormatter())

    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)

    if app:
        init_middleware(app)

    return logger


def init_middleware(app: Flask):
    @app.before_request
    def start_timer():
        g.start_time = time.perf_counter()
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.rid = rid

    @app.after_request
    def log_request(response):
        if request.path.startswith("/static"):
            return response

        duration_ms = int((time.perf_counter() - getattr(g, "start_time", time.perf_counter())) * 1000)
        rid = getattr(g, "rid", "-")
        
        # We can't easily get tenant_id here without more context, 
        # but if it's in g, we could use it.
        tenant_id = getattr(g, "tenant_id", None)

        log_extra = {
            "rid": rid,
            "method": request.method,
            "route": request.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "tenant_id": tenant_id
        }

        logger = logging.getLogger("kukanilea")
        logger.info(f"{request.method} {request.path}", extra=log_extra)
        
        response.headers["X-Request-ID"] = rid
        return response
