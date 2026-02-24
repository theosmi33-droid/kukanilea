"""
scripts/update_server/serve.py
Statischer File-Server für KUKANILEA Gold Updates.
Liefert Manifeste und signierte ZIP-Archive vom NAS aus.
"""
import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 8080
# Priorisierte Pfade für die Update-Quelle
UPDATE_SOURCES = [
    Path("/Volumes/KUKANILEA-ENDKUNDE/updates"),
    Path("/KUKANILEA-ENDKUNDE/updates"),
    Path("./updates")
]

class UpdateHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Suche das erste existierende Verzeichnis
        self.source_dir = None
        for src in UPDATE_SOURCES:
            if src.exists() and src.is_dir():
                self.source_dir = src
                break
        
        if not self.source_dir:
            print("❌ Fehler: Kein Update-Verzeichnis auf dem NAS gefunden!")
            sys.exit(1)
            
        super().__init__(*args, directory=str(self.source_dir), **kwargs)

    def end_headers(self):
        # CORS erlauben, damit die App das Manifest laden kann
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

def run_server():
    print(f"🚀 KUKANILEA Update-Server gestartet.")
    print(f"📂 Quelle: {Path().resolve()}")
    print(f"🌐 Adresse: http://localhost:{PORT}")
    print(f"🔗 NAS-Pfad: smb://192.168.0.2/KUKANILEA-ENDKUNDE/updates")
    
    with socketserver.TCPServer(("", PORT), UpdateHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("
🛑 Server beendet.")

if __name__ == "__main__":
    run_server()
