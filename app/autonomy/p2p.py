"""
app/autonomy/p2p.py
Peer-to-Peer Discovery Service für KUKANILEA v2.0.
Erlaubt das Finden von anderen Instanzen im lokalen Netzwerk (LAN/WLAN) via mDNS.
"""

import socket
import logging
from zeroconf import IPVersion, ServiceInfo, Zeroconf, ServiceBrowser

logger = logging.getLogger("kukanilea.p2p")

class KukanileaDiscovery:
    def __init__(self, port=5051):
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self.port = port
        self.service_type = "_kukanilea._tcp.local."
        self.peers = {}

    def advertise(self, hostname):
        """Macht die eigene Instanz im Netzwerk sichtbar."""
        local_ip = socket.gethostbyname(socket.gethostname())
        info = ServiceInfo(
            self.service_type,
            f"{hostname}.{self.service_type}",
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties={"version": "1.2.0", "type": "master"},
            server=f"{hostname}.local.",
        )
        self.zeroconf.register_service(info)
        logger.info(f"P2P: Werbe als {hostname} auf {local_ip}:{self.port}")

    def find_peers(self):
        """Sucht aktiv nach anderen KUKANILEA Instanzen."""
        class MyListener:
            def remove_service(self, zc, type, name):
                logger.info(f"Service {name} entfernt")

            def add_service(self, zc, type, name):
                info = zc.get_service_info(type, name)
                if info:
                    logger.info(f"Peer gefunden: {name} auf {socket.inet_ntoa(info.addresses[0])}")

        browser = ServiceBrowser(self.zeroconf, self.service_type, listener=MyListener())
        return browser

    def stop(self):
        self.zeroconf.unregister_all_services()
        self.zeroconf.close()
