from __future__ import annotations

import os

from flask import Flask


def init_otel(app: Flask) -> None:
    enabled = os.environ.get("KUK_OTEL_ENABLED", "0") == "1"
    if not enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        trace.set_tracer_provider(TracerProvider())
        FlaskInstrumentor().instrument_app(app)

        # Local only: Console exporter
        span_processor = BatchSpanProcessor(ConsoleSpanExporter())
        trace.get_tracer_provider().add_span_processor(span_processor)
        
    except ImportError:
        app.logger.warning("OpenTelemetry requested but dependencies (opentelemetry-sdk, opentelemetry-instrumentation-flask) not found.")
