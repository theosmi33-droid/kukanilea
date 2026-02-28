from __future__ import annotations

from typing import Any, Dict, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.core.mesh_network import MeshNetworkManager
from flask import current_app

class MeshSyncTool(BaseTool):
    """
    Tool for manually triggering a synchronization with a peer Hub.
    """

    name = "mesh_sync"
    description = "Initiiert eine Synchronisation mit einem anderen KUKANILEA Hub."
    input_schema = {
        "type": "object",
        "properties": {
            "peer_ip": {"type": "string", "description": "Die IP-Adresse des Ziel-Hubs."},
            "peer_port": {"type": "integer", "default": 5051}
        },
        "required": ["peer_ip"]
    }

    def run(self, peer_ip: str, peer_port: int = 5051) -> Any:
        auth_db = current_app.extensions.get("auth_db")
        if not auth_db:
            return {"error": "Database not initialized."}
            
        manager = MeshNetworkManager(auth_db)
        success = manager.initiate_handshake(peer_ip, peer_port)
        
        if success:
            return {
                "status": "success",
                "message": f"Verbindung zu Hub unter {peer_ip} erfolgreich hergestellt und synchronisiert."
            }
        else:
            return {"error": f"Verbindung zu Hub unter {peer_ip} fehlgeschlagen."}

# Register tool
registry.register(MeshSyncTool())
