from __future__ import annotations

import logging
import uuid

from flask import g, request


def init_request_logging(app) -> None:
    logger = logging.getLogger("kukanilea")
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s",
        )

        old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            try:
                record.request_id = getattr(g, "request_id", "-")
            except Exception:
                record.request_id = "-"
            return record

        logging.setLogRecordFactory(record_factory)

    class RequestIdFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "request_id"):
                record.request_id = "-"
            return True

    logger.addFilter(RequestIdFilter())

    @app.before_request
    def _assign_request_id():
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def _attach_request_id(response):
        rid = getattr(g, "request_id", None)
        if rid:
            response.headers["X-Request-Id"] = rid
        return response
