from __future__ import annotations

import json
import logging
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import Config
from app.core.mesh_identity import ensure_mesh_identity, sign_message, verify_signature

logger = logging.getLogger("kukanilea.mesh_network")

class MeshNetworkManager:
    """
    Manages peer Hubs and synchronization over the internet.
    Uses Ed25519 signatures for Hub-to-Hub authentication.
    """

    def __init__(self, auth_db):
        self.auth_db = auth_db
        self.pub_key, self.node_id = ensure_mesh_identity()

    def register_peer(self, node_id: str, name: str, public_key: str, last_ip: str):
        """Registers a new peer Hub in the local database."""
        with self.auth_db._db() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO mesh_nodes (node_id, name, public_key, last_ip, last_seen, status)
                VALUES (?, ?, ?, ?, ?, 'OFFLINE')
                """,
                (node_id, name, public_key, last_ip, datetime.now(timezone.utc).isoformat() + "Z")
            )
            con.commit()

    def get_peers(self) -> List[Dict[str, Any]]:
        """Returns a list of all known peer Hubs."""
        with self.auth_db._db() as con:
            rows = con.execute("SELECT * FROM mesh_nodes").fetchall()
            return [dict(r) for r in rows]

    def initiate_handshake(self, peer_ip: str, peer_port: int = 5051) -> bool:
        """Attempts to connect to a peer Hub and exchange identity."""
        url = f"http://{peer_ip}:{peer_port}/api/mesh/handshake"
        
        payload = {
            "node_id": self.node_id,
            "name": Config.get_branding().get("app_name", "KUKANILEA Hub"),
            "public_key": self.pub_key,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }
        
        # Sign the payload to prove identity
        sig = sign_message(json.dumps(payload, sort_keys=True).encode('utf-8'))
        
        try:
            resp = requests.post(url, json={"data": payload, "signature": sig}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                peer_info = data.get("peer")
                if peer_info:
                    # Verify peer's response signature
                    peer_sig = data.get("signature")
                    peer_data = data.get("peer")
                    if verify_signature(peer_info["public_key"], json.dumps(peer_data, sort_keys=True).encode('utf-8'), peer_sig):
                        self.register_peer(
                            peer_info["node_id"],
                            peer_info["name"],
                            peer_info["public_key"],
                            peer_ip
                        )
                        logger.info(f"Handshake successful with {peer_info['node_id']}")
                        return True
            return False
        except Exception as e:
            logger.error(f"Handshake failed with {peer_ip}: {e}")
            return False

    def sync_with_peer(self, peer_node_id: str) -> bool:
        """Sends local CRDT patches to a peer Hub."""
        # TODO: Implement real CRDT patch exchange
        # For POC, we just update 'last_seen'
        with self.auth_db._db() as con:
            con.execute(
                "UPDATE mesh_nodes SET last_seen = ?, status = 'ONLINE' WHERE node_id = ?",
                (datetime.now(timezone.utc).isoformat() + "Z", peer_node_id)
            )
            con.commit()
        return True
