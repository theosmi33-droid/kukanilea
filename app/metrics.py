"""
app/metrics.py
Prometheus Metriken Endpunkt für Live-Monitoring und Benchmarking.
"""

from flask import Blueprint, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

bp = Blueprint('metrics', __name__)

# Basic Metriken
REQUEST_COUNT = Counter(
    'kukanilea_request_count', 
    'Anzahl der Application Requests',
    ['method', 'endpoint', 'http_status']
)

REQUEST_LATENCY = Histogram(
    'kukanilea_request_latency_seconds', 
    'Request Latenz in Sekunden',
    ['endpoint']
)

OCR_QUEUE_SIZE = Histogram(
    'kukanilea_ocr_queue_size',
    'Größe der OCR Queue'
)

@bp.route('/metrics')
def metrics():
    """Gibt Prometheus-formatierte Metriken zurück."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
