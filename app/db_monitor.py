"""
Database-Performance-Monitoring für KUKANILEA.
"""
import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def query_profiler(query_name: str, threshold_ms: float = 100.0):
    """
    Context-Manager für Query-Profiling.
    
    Usage:
        with query_profiler("get_contacts"):
            cursor = conn.execute("SELECT ...")
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        
        # Log slow queries
        if duration_ms > threshold_ms:
            logger.warning(f"Slow query: {query_name} took {duration_ms:.1f}ms (threshold: {threshold_ms}ms)")
        else:
            logger.debug(f"Query: {query_name} took {duration_ms:.1f}ms")
        
        # Metrics could be integrated here (e.g. Prometheus/StatsD)
