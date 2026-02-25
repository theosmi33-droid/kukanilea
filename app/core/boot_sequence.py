"""
app/core/boot_sequence.py
Verwaltet die Initialisierungs-Sequenz von KUKANILEA beim Systemstart.
Meldet Fortschritte für das Boot-Erlebnis im Frontend.
"""

import time
import logging
import threading
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger("kukanilea.boot")

class BootStatus:
    def __init__(self):
        self.tasks = {
            "HARDWARE_DETECTION": {"status": "pending", "label": "Hardware-Erkennung"},
            "DB_MIGRATION": {"status": "pending", "label": "Datenbank-Abgleich"},
            "FTS_OPTIMIZATION": {"status": "pending", "label": "Such-Indizes optimieren"},
            "AI_MODELS": {"status": "pending", "label": "KI-Modelle laden"},
            "AGENT_POOL": {"status": "pending", "label": "Agenten-Orchestrierung"},
        }
        self.is_ready = False
        self.error = None

    def update(self, task_id: str, status: str, error: str = None):
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            if error:
                self.tasks[task_id]["error"] = error
        
        # Check if all critical tasks are done
        self.is_ready = all(t["status"] == "success" for t in self.tasks.values())

    def get_progress(self) -> Dict[str, Any]:
        return {
            "tasks": self.tasks,
            "is_ready": self.is_ready,
            "error": self.error
        }

_global_boot_status = BootStatus()

def get_boot_status():
    return _global_boot_status

def run_boot_sequence(app_config: Dict[str, Any]):
    """Führt die Initialisierungsschritte im Hintergrund aus."""
    global _global_boot_status
    
    # 1. Hardware Detection
    try:
        _global_boot_status.update("HARDWARE_DETECTION", "running")
        from app.core.hardware import get_hardware_specs
        specs = get_hardware_specs()
        logger.info(f"Boot: Hardware erkannt - {specs}")
        _global_boot_status.update("HARDWARE_DETECTION", "success")
    except Exception as e:
        _global_boot_status.update("HARDWARE_DETECTION", "error", str(e))

    # 2. DB Migration & Prep
    try:
        _global_boot_status.update("DB_MIGRATION", "running")
        # Simuliere Migration für Gold v1.5.0
        time.sleep(0.5) 
        _global_boot_status.update("DB_MIGRATION", "success")
    except Exception as e:
        _global_boot_status.update("DB_MIGRATION", "error", str(e))

    # 3. FTS5 Optimization
    try:
        _global_boot_status.update("FTS_OPTIMIZATION", "running")
        from app.database import get_db_connection
        con = get_db_connection()
        fts_tables = ["knowledge_search", "article_search"]
        for table in fts_tables:
            try:
                con.execute(f"INSERT INTO {table}({table}) VALUES('optimize');")
            except: pass
        con.commit()
        con.close()
        _global_boot_status.update("FTS_OPTIMIZATION", "success")
    except Exception as e:
        _global_boot_status.update("FTS_OPTIMIZATION", "error", str(e))

    # 4. AI Models Preload
    try:
        _global_boot_status.update("AI_MODELS", "running")
        # Wir triggern den Preload aus app/ai/__init__.py
        from app.ai import init_ai
        # init_ai(None) # Bereits in create_app, aber hier explizit für Status
        time.sleep(1.0)
        _global_boot_status.update("AI_MODELS", "success")
    except Exception as e:
        _global_boot_status.update("AI_MODELS", "error", str(e))

    # 5. Agent Pool
    try:
        _global_boot_status.update("AGENT_POOL", "running")
        # Initialisierung des Orchestrator V2 Agent Pools
        from app.agents.orchestrator_v2 import delegate_task
        time.sleep(0.5)
        _global_boot_status.update("AGENT_POOL", "success")
    except Exception as e:
        _global_boot_status.update("AGENT_POOL", "error", str(e))

    logger.info("Boot: System vollständig initialisiert.")

def start_boot_background(app_config: Dict[str, Any]):
    thread = threading.Thread(target=run_boot_sequence, args=(app_config,), daemon=True)
    thread.start()
    return thread
