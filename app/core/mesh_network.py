from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from app.config import Config
from app.core.mesh_identity import (
    HANDSHAKE_ACK_PURPOSE,
    HANDSHAKE_INIT_PURPOSE,
    create_handshake_envelope,
    verify_handshake_envelope,
)

logger = logging.getLogger("kukanilea.mesh_network")


class MeshNetworkManager:
    """
    Manages peer Hubs and synchronization over the internet.
    Uses signed challenge-response handshakes for Hub authentication.
    """

    def __init__(self, auth_db):
        self.auth_db = auth_db

    def register_peer(self, node_id: str, name: str, public_key: str, last_ip: str):
        """Registers a new peer Hub in the local database."""
        with self.auth_db._db() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO mesh_nodes (node_id, name, public_key, last_ip, last_seen, status)
                VALUES (?, ?, ?, ?, ?, 'OFFLINE')
                """,
                (
                    node_id,
                    name,
                    public_key,
                    last_ip,
                    datetime.now(timezone.utc).isoformat() + "Z",
                ),
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

        challenge = secrets.token_urlsafe(24)
        request_envelope = create_handshake_envelope(
            name=Config.get_branding().get("app_name", "KUKANILEA Hub"),
            purpose=HANDSHAKE_INIT_PURPOSE,
            challenge=challenge,
        )

        try:
            resp = requests.post(url, json=request_envelope, timeout=10)
            if resp.status_code != 200:
                return False

            ok, reason, peer_info = verify_handshake_envelope(
                resp.json(),
                expected_purpose=HANDSHAKE_ACK_PURPOSE,
                expected_challenge=challenge,
            )
            if not ok or not peer_info:
                logger.warning("Handshake rejected for %s: %s", peer_ip, reason)
                return False

            self.register_peer(
                str(peer_info["node_id"]),
                str(peer_info["name"]),
                str(peer_info["public_key"]),
                peer_ip,
            )
            logger.info("Handshake successful with %s", peer_info["node_id"])
            return True
        except Exception as e:
            logger.error("Handshake failed with %s: %s", peer_ip, e)
            return False

    def sync_with_peer(self, peer_node_id: str) -> bool:
        """Sends local CRDT patches to a peer Hub."""
        # TODO: Implement real CRDT patch exchange
        # For POC, we just update 'last_seen'
        with self.auth_db._db() as con:
            con.execute(
                "UPDATE mesh_nodes SET last_seen = ?, status = 'ONLINE' WHERE node_id = ?",
                (datetime.now(timezone.utc).isoformat() + "Z", peer_node_id),
            )
            con.commit()
        return True
