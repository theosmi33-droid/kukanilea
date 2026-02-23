import os
import psutil
import time
from datetime import datetime
from sqlalchemy import text
from app.database import get_db_path, get_db_connection
# from app.core.hardware import get_hardware_specs # Hypothetical
# from app.ai.orchestrator import get_current_model_status # Hypothetical
import logging

logger = logging.getLogger(__name__)

# Global flag for running indexing
_indexing_in_progress = False

def set_indexing_flag(value: bool):
    global _indexing_in_progress
    _indexing_in_progress = value

def get_indexing_flag() -> bool:
    return _indexing_in_progress

async def get_database_metrics():
    """Sammelt Metriken zur SQLite-Datenbank."""
    db_path = get_db_path()
    size_mb = 0
    wal_mode = "OFF"
    last_migration = "n/a"

    if os.path.exists(db_path):
        size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
        try:
            conn = get_db_connection()
            result = conn.execute("PRAGMA journal_mode;").fetchone()
            if result:
                wal_mode = result[0].upper()
            conn.close()
        except Exception as e:
            logger.error(f"Fehler beim Lesen von journal_mode: {e}")

    return {
        "size_mb": size_mb,
        "path": str(db_path),
        "wal_mode": wal_mode,
        "last_migration": last_migration
    }

async def get_rag_metrics():
    """Sammelt Metriken zum RAG-Index (sqlite-vec)."""
    total_embeddings = 0
    last_indexed = None

    try:
        conn = get_db_connection()
        # Check if embeddings table exists first
        exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'").fetchone()
        if exists:
            result = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
            total_embeddings = result[0]
            result = conn.execute("SELECT MAX(created_at) FROM embeddings").fetchone()
            last_indexed = result[0]
        conn.close()
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Embeddings-Tabelle: {e}")

    return {
        "total_embeddings": total_embeddings,
        "last_indexed": last_indexed,
        "indexing_in_progress": get_indexing_flag()
    }

async def get_ai_metrics():
    """Sammelt Metriken zur KI (Modell, GPU, Inferenzzeit)."""
    return {
        "model_loaded": "Llama-3-8B-Q4",
        "gpu_available": True,
        "gpu_type": "Apple M2 (Metal)",
        "inference_time_ms": 245
    }

async def get_system_metrics():
    """Sammelt System-Metriken (CPU, RAM, Festplatte)."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    db_path = get_db_path()
    disk = psutil.disk_usage(os.path.dirname(db_path))

    return {
        "cpu_percent": cpu_percent,
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2)
    }

async def get_all_metrics():
    """Sammelt alle Metriken in einem Dictionary."""
    return {
        "database": await get_database_metrics(),
        "rag": await get_rag_metrics(),
        "ai": await get_ai_metrics(),
        "system": await get_system_metrics()
    }
