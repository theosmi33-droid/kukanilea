"""
app/agents/sync_worker.py
Automatisierter Hintergrund-Dienst für den Global Mesh Sync.
Koordiniert den Datenaustausch zwischen Hubs und Clients.
"""

import time
import logging
import threading
import requests
from typing import List, Dict, Any
from app.core.p2p_sync import mesh_manager
from app.core.crdt_engine import crdt
from app.core.mesh_logic import get_latest_changes, apply_remote_delta

logger = logging.getLogger("kukanilea.sync")

class SyncWorker:
    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self.running = False
        self._thread = None
        self.last_sync_ts = 0

    def start(self):
        """Startet den Sync-Loop im Hintergrund."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"Sync-Worker gestartet (Intervall: {self.interval}s)")

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            try:
                self._perform_sync_cycle()
            except Exception as e:
                logger.error(f"Fehler im Sync-Cycle: {e}")
            
            time.sleep(self.interval)

    def _perform_sync_cycle(self):
        """Führt einen vollständigen Abgleich mit allen bekannten Peers durch."""
        if not mesh_manager:
            return

        peers = mesh_manager.get_active_peers()
        if not peers:
            return

        # 1. Lokale Änderungen seit letztem Sync ermitteln
        # In der Praxis würden wir hier pro Peer tracken, was gesendet wurde.
        # Für v1.6.0 nutzen wir den Lamport-Zeitstempel.
        changes = get_latest_changes(since_ts=str(self.last_sync_ts))
        
        for peer in peers:
            peer_url = f"http://{peer['address']}:{peer['port']}/api/p2p/sync/request"
            try:
                logger.info(f"Mesh: Starte Abgleich mit {peer['address']}...")
                
                # Sende lokale Änderungen an Peer
                response = requests.post(peer_url, json={
                    "id": mesh_manager.instance_id,
                    "delta": changes,
                    "timestamp": int(time.time())
                }, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    # Wenn der Peer uns ebenfalls Änderungen schickt, wenden wir sie an
                    if "delta" in data:
                        apply_remote_delta(data["delta"])
                    
                    logger.info(f"✅ Sync mit {peer['address']} erfolgreich.")
            except Exception as e:
                logger.warning(f"⚠️ Sync mit {peer['address']} fehlgeschlagen: {e}")

        # Update den lokalen Fortschritts-Marker
        self.last_sync_ts = crdt.local_clock if crdt else 0

# Singleton
sync_worker = SyncWorker()

def start_sync_worker(interval: int = 60):
    sync_worker.interval = interval
    sync_worker.start()
    return sync_worker
