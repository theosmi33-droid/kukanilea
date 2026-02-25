"""
app/core/observer.py
Überwacht den permanenten Zustand der KUKANILEA-Subsysteme (Heartbeat).
Meldet Auslastung und Verfügbarkeit an die UI.
"""

import os
import psutil
import socket
import logging
import sqlite3
from typing import Dict, Any
from app.config import Config

logger = logging.getLogger("kukanilea.observer")

class SystemObserver:
    def __init__(self):
        self.db_path = Config.CORE_DB

    def check_ollama(self) -> bool:
        """Prüft ob der lokale Ollama-Server antwortet."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            # Standardport 11434
            s.connect(("127.0.0.1", 11434))
            return True
        except:
            return False
        finally:
            s.close()

    def check_ocr(self) -> bool:
        """Prüft ob Tesseract im Systempfad verfügbar ist."""
        import shutil
        return shutil.which("tesseract") is not None

    def get_db_stats(self) -> Dict[str, Any]:
        try:
            size_bytes = os.path.getsize(Config.CORE_DB) if os.path.exists(Config.CORE_DB) else 0
            return {
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "healthy": True
            }
        except:
            return {"size_mb": 0, "healthy": False}

    def get_system_load(self) -> Dict[str, float]:
        """Ermittelt aktuelle CPU und RAM Auslastung."""
        return {
            "cpu_pct": psutil.cpu_percent(),
            "ram_pct": psutil.virtual_memory().percent
        }

    def get_full_status(self) -> Dict[str, Any]:
        return {
            "ollama": "online" if self.check_ollama() else "offline",
            "ocr": "ready" if self.check_ocr() else "missing",
            "db": self.get_db_stats(),
            "load": self.get_system_load(),
            "timestamp": os.getpid() # Einfacher Heartbeat-Indikator
        }

_observer_instance = SystemObserver()

def get_system_status():
    return _observer_instance.get_full_status()
