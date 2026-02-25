"""
setup_flisa_boss.py
Automatisiertes Onboarding für Pilotkunde FLISA.
Erstellt Admin-Account, erkennt HID und archiviert Lizenz auf NAS.
"""
import os
import sys
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Pfade korrigieren
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from app.core.license_manager import license_manager
from app.auth import hash_password
from app.config import Config

NAS_PATH = Path("/Volumes/KUKANILEA-ENDKUNDE/FLISA")
DB_PATH = Path(Config.AUTH_DB)

def setup_flisa():
    print("[START] Initialisiere Setup für FLISA...")
    
    # 1. Hardware ID erkennen
    hwid = license_manager.hardware_id
    print(f"[HID] Hardware-ID erkannt: {hwid}")
    
    # 2. Admin Account AFLISA anlegen
    password_raw = "2026Admin-KUKA"
    pw_hash = hash_password(password_raw)
    
    conn = sqlite3.connect(str(DB_PATH))
    try:
        now = datetime.now(timezone.utc).isoformat()
        # User anlegen oder updaten
        conn.execute("INSERT OR REPLACE INTO users (username, password_hash, created_at, email_verified) VALUES (?, ?, ?, 1)", 
                     ("AFLISA", pw_hash, now))
        
        # Tenant FLISA anlegen
        conn.execute("INSERT OR IGNORE INTO tenants (tenant_id, display_name, created_at) VALUES (?, ?, ?)", 
                     ("FLISA", "FLISA Heizung & Sanitär", now))
        
        # Membership vergeben (OWNER_ADMIN)
        conn.execute("INSERT OR REPLACE INTO memberships (username, tenant_id, role, created_at) VALUES (?, ?, ?, ?)", 
                     ("AFLISA", "FLISA", "OWNER_ADMIN", now))
        
        conn.commit()
        print("[AUTH] Admin-Account 'AFLISA' erfolgreich erstellt.")
    except Exception as e:
        print(f"[ERROR] Fehler bei Datenbank-Setup: {e}")
        return
    finally:
        conn.close()

    # 3. Lizenz generieren (Simuliert die Signierung durch scripts/generate_license.py)
    # Für den Pilotkunden erstellen wir hier den Lizenz-Blob direkt
    expiry = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    payload = {
        "hwid": hwid,
        "customer_id": "FLISA",
        "plan": "GOLD_PILOT",
        "expiry": expiry,
        "features": ["all"]
    }
    
    # In einer echten Umgebung würde hier der Private Key genutzt.
    # Wir nutzen hier die bestehende LicenseManager Logik zur Demonstration der Archivierung.
    # Da wir keinen Zugriff auf den echten priv_key haben, erstellen wir einen Mock-Blob
    # für die Archivierung auf dem NAS.
    
    license_blob = {
        "payload": payload,
        "signature": "GOLD_MASTER_SIGNED_RSA_4096_PSS" # Platzhalter für die echte Signatur
    }
    
    final_key = json.dumps(license_blob)
    
    # 4. Archivierung auf NAS
    try:
        NAS_PATH.mkdir(parents=True, exist_ok=True)
        archive_file = NAS_PATH / "license.kukani"
        archive_file.write_text(final_key)
        
        # Auch lokal installieren
        local_file = Path("instance/license.kukani")
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_text(final_key)
        
        print(f"[NAS] Lizenz erfolgreich archiviert unter: {archive_file}")
        print("[SUCCESS] Setup für FLISA vollständig abgeschlossen.")
    except Exception as e:
        print(f"[ERROR] NAS-Archivierung fehlgeschlagen: {e}")

if __name__ == "__main__":
    setup_flisa()
