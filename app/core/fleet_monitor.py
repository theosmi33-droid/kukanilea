"""
app/core/fleet_monitor.py
Zentrales Dashboard für Flotten-Telemetrie und Global Mesh Health.
Sammelt asynchron Heartbeats und aggregiert Hardware-Vitals.
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("kukanilea.fleet")

# In-Memory Storage um SSD-Schreibzugriffe (ZimaBlade) zu schonen
PEER_HEARTBEATS: Dict[str, Dict[str, Any]] = {}

def record_heartbeat(payload: Dict[str, Any]):
    """Registriert einen Heartbeat von einem Mesh-Peer."""
    peer_id = payload.get("peer_id")
    if not peer_id:
        return
    
    PEER_HEARTBEATS[peer_id] = {
        **payload,
        "last_seen": time.time(),
        "status": "online"
    }
    logger.debug(f"Heartbeat empfangen von {peer_id}")

def get_fleet_status() -> List[Dict[str, Any]]:
    """Gibt den aggregierten Status aller bekannten Peers zurück."""
    now = time.time()
    fleet = []
    
    try:
        from app.web import _audit
    except ImportError:
        def _audit(action, target, meta=None): pass

    for peer_id, data in list(PEER_HEARTBEATS.items()):
        last_seen = data.get("last_seen", 0)
        
        # Timeout nach 5 Minuten (300 Sekunden)
        if now - last_seen > 300 and data.get("status") != "offline":
            data["status"] = "offline"
            logger.warning(f"🚨 Peer {peer_id} ist OFFLINE (Timeout).")
            try:
                _audit("peer_offline", target=peer_id, meta={"last_seen": last_seen})
            except Exception:
                pass
                
        fleet.append(data)
        
    return fleet

def get_backup_status() -> Dict[str, Any]:
    """Liest den letzten Eintrag des Immutable Backup Vaults."""
    backup_file = Path("internal_vault/backup_history.json")
    if not backup_file.exists():
        return {"status": "NO_BACKUP", "text": "Kein Backup gefunden", "verified": False}
        
    try:
        with open(backup_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if not lines:
                return {"status": "NO_BACKUP", "text": "Backup-Log leer", "verified": False}
            
            last_entry = json.loads(lines[-1])
            ts_str = last_entry.get("timestamp", "")
            
            is_verified = last_entry.get("status") == "SUCCESS"
            
            # Simple Time Parsing für UI
            from datetime import datetime, timezone
            import math
            try:
                backup_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                delta_minutes = math.floor((datetime.now(timezone.utc) - backup_time).total_seconds() / 60)
                time_text = f"Vor {delta_minutes} Min"
            except Exception:
                time_text = ts_str
            
            return {
                "status": "OK" if is_verified else "ERROR",
                "text": time_text,
                "verified": is_verified
            }
    except Exception as e:
        logger.error(f"Fehler beim Lesen des Backup-Status: {e}")
        return {"status": "ERROR", "text": "Fehler beim Lesen", "verified": False}
