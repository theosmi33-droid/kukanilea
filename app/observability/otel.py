from __future__ import annotations

import os
import logging
from flask import Flask

logger = logging.getLogger("kukanilea.otel")

def setup_otel(app: Flask):
    enabled = os.environ.get("KUK_OTEL_ENABLED", "0") == "1"
    if not enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        
        # SOURCE: https://opentelemetry.io/docs/languages/python/exporters/
        # Console exporter is correct for local debug
        
        provider = TracerProvider()
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        
        FlaskInstrumentor().instrument_app(app)
        logger.info("Local OpenTelemetry (Console) active.")
        
    except ImportError:
        logger.warning("OpenTelemetry packages missing. Skipping instrumentation.")
