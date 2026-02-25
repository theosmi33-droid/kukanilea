"""
app/core/crdt_engine.py
Kern-Engine für konfliktfreie replizierte Datentypen (CRDT).
Implementiert LWW-Element-Set (Last-Writer-Wins) für SQLite-Zeilen.
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("kukanilea.crdt")

class CRDTEngine:
    """
    Verwaltet Lamport-Zeitstempel und Konfliktlösung.
    Jeder Datensatz erhält ein Triple: (Value, Timestamp, NodeID).
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.local_clock = 0

    def get_next_timestamp(self) -> int:
        """Generiert den nächsten Lamport-Zeitstempel."""
        self.local_clock += 1
        # Wir kombinieren Unix-Zeit (Sekunden) mit der Lamport-Clock für Präzision
        return int(time.time() * 1000) + self.local_clock

    def resolve_conflict(self, local_data: Dict[str, Any], remote_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Löst Konflikte basierend auf dem Last-Writer-Wins (LWW) Prinzip.
        Erwartet in den Daten ein Feld 'lamport_ts'.
        """
        local_ts = local_data.get("lamport_ts", 0)
        remote_ts = remote_data.get("lamport_ts", 0)

        if remote_ts > local_ts:
            logger.info(f"CRDT: Remote gewinnt ({remote_ts} > {local_ts})")
            return remote_data
        
        elif remote_ts == local_ts:
            # Bei exakt gleichem Zeitstempel entscheidet die lexikographische NodeID (Tie-Breaker)
            remote_node = remote_data.get("node_id", "")
            local_node = local_data.get("node_id", self.node_id)
            if remote_node > local_node:
                return remote_data
        
        return local_data

    def prepare_for_sync(self, table_name: str, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bereitet lokale Daten für den Versand an einen anderen Hub vor."""
        row_data["node_id"] = self.node_id
        if "lamport_ts" not in row_data:
            row_data["lamport_ts"] = self.get_next_timestamp()
        return row_data

# Singleton-Instanz (wird mit der Instance-ID aus dem MeshManager initialisiert)
crdt = None

def init_crdt(node_id: str):
    global crdt
    crdt = CRDTEngine(node_id)
    return crdt
