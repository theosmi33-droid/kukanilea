"""
app/core/network.py
Netzwerk-Utilities für KUKANILEA.
Fokus: Lokale IP-Erkennung und QR-Code Generierung für Mobile-Pairing.
"""

import socket
import qrcode
import io
import base64
import logging

logger = logging.getLogger("kukanilea.network")

def get_local_ip() -> str:
    """Ermittelt die primäre lokale IP-Adresse des Hosts."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Erfordert keine echte Internetverbindung
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generate_pairing_qr(port: int = 5051) -> str:
    """Generiert einen QR-Code als Base64-String für die mobile Koppelung."""
    ip = get_local_ip()
    url = f"http://{ip}:{port}/mobile/capture"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    logger.info(f"Pairing QR-Code generiert für: {url}")
    return img_str
