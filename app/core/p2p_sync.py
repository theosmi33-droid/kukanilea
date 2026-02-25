"""
app/core/p2p_sync.py
Lokaler Peer-to-Peer Sync Manager für KUKANILEA.
Nutzt Zeroconf (mDNS) zur automatischen Erkennung von Instanzen im WLAN.
"""

import socket
import logging
import threading
import time
from typing import Dict, List, Optional
from zeroconf import IPVersion, ServiceInfo, Zeroconf, ServiceBrowser, ServiceStateChange

logger = logging.getLogger("kukanilea.p2p")

class MeshManager:
    def __init__(self, port: int = 5051):
        self.port = port
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self.peers: Dict[str, Dict] = {}
        self.local_ip = self._get_ip()
        self.instance_id = f"KUKANI-{socket.gethostname()}-{self.local_ip.split('.')[-1]}"
        
        self.service_info = ServiceInfo(
            "_kukanilea._tcp.local.",
            f"{self.instance_id}._kukanilea._tcp.local.",
            addresses=[socket.inet_aton(self.local_ip)],
            port=self.port,
            properties={"version": "1.5.0", "id": self.instance_id},
        )

    def _get_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start(self):
        """Registriert den eigenen Dienst und startet das Browsing."""
        logger.info(f"P2P: Registriere Instanz {self.instance_id} auf {self.local_ip}:{self.port}")
        
        # Initialisiere CRDT mit der lokalen Instanz-ID
        from .crdt_engine import init_crdt
        init_crdt(self.instance_id)
        
        self.zeroconf.register_service(self.service_info)
        self.browser = ServiceBrowser(self.zeroconf, "_kukanilea._tcp.local.", handlers=[self._on_service_state_change])

    def stop(self):
        self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()

    def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange):
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                address = socket.inet_ntoa(info.addresses[0])
                if address != self.local_ip:
                    peer_id = info.properties.get(b'id', b'unknown').decode()
                    self.peers[peer_id] = {
                        "name": name,
                        "address": address,
                        "port": info.port,
                        "last_seen": time.time()
                    }
                    logger.info(f"✨ P2P: Neuer Peer gefunden: {peer_id} @ {address}:{info.port}")
        
        elif state_change is ServiceStateChange.Removed:
            # Identifikation über Name, da info nicht mehr abrufbar
            to_remove = [k for k, v in self.peers.items() if v["name"] == name]
            for k in to_remove:
                logger.info(f"🔌 P2P: Peer getrennt: {k}")
                del self.peers[k]

    def get_active_peers(self) -> List[Dict]:
        return list(self.peers.values())

# Globaler Manager (wird in app/__init__.py gestartet)
mesh_manager = None

def init_mesh(port: int = 5051):
    global mesh_manager
    mesh_manager = MeshManager(port=port)
    # Start im Hintergrund-Thread um Boot nicht zu blockieren
    thread = threading.Thread(target=mesh_manager.start, daemon=True)
    thread.start()
    return mesh_manager
