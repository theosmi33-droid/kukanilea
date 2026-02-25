from __future__ import annotations

from flask import Flask

from .logging_json import init_json_logging
from .otel import init_otel


def init_observability(app: Flask) -> None:
    init_json_logging(app)
    init_otel(app)
