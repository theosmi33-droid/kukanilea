"""
app/core/hub_metrics.py
Hardware-Überwachung für den Workshop-Hub (ZimaBlade).
Fokus: Temperatur, SSD-Wear und NAS-Spiegelung.
"""

import psutil
import logging
import os
from typing import Dict, Any

logger = logging.getLogger("kukanilea.hub")

def get_hub_vitals() -> Dict[str, Any]:
    """Ermittelt kritische Hardware-Metriken für den lüfterlosen Hub."""
    vitals = {
        "cpu_usage_percent": psutil.cpu_percent(interval=1),
        "memory_usage_gb": round(psutil.virtual_memory().used / (1024**3), 2),
        "disk_usage_percent": psutil.disk_usage('/').percent,
        "throttled": False
    }

    # Temperatur (ZimaBlade lüfterlos -> Kritisch)
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            vitals["cpu_temp"] = temps['coretemp'][0].current
            if vitals["cpu_temp"] > 85:
                vitals["throttled"] = True
                logger.warning("🚨 HUB TEMP KRITISCH: Drosselung aktiv!")
    except:
        vitals["cpu_temp"] = "N/A"

    # NAS Check (Prüfung ob externe Mirror-Partition gemountet ist)
    nas_path = os.environ.get("KUKANILEA_NAS_PATH", "/mnt/nas_vault")
    vitals["nas_synced"] = os.path.ismount(nas_path)
    
    return vitals
