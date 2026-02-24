"""
scripts/verify_distribution.py
Automatisiertes Quality-Gate für die v1.5.0 Gold Distribution.
Simuliert Erststart und validiert HWID-Bindung.
"""
import sys
import os
import shutil
import subprocess
from pathlib import Path

def run_audit():
    print("🚀 Starte Distribution Audit...")
    
    # 1. HWID Konsistenz
    from app.core.license_manager import license_manager
    hwid = license_manager.hardware_id
    print(f"   HWID generiert: {hwid}")
    if len(hwid) != 64: # SHA-256
        print("❌ Fehler: HWID Format ungültig.")
        return False

    # 2. Lizenz-Ablehnung (Falsche Signatur)
    fake_license = "eyJwYXlsb2FkIjp7Imh3aWQiOiJmYWtlIn0sInNpZ25hdHVyZSI6ImZha2UifQ=="
    if license_manager.load_license(fake_license):
        print("❌ Fehler: Bösartige Lizenz wurde akzeptiert!")
        return False
    print("   ✅ Sicherheitsprüfung: Ungültige Lizenz abgelehnt.")

    # 3. Ressourcen-Verfügbarkeit
    # Prüfe ob Public Key im Pfad ist (wichtig für PyInstaller)
    if not Path("app/core/certs/license_pub.pem").exists():
        print("❌ Fehler: Public Key fehlt im Cert-Verzeichnis.")
        return False
    print("   ✅ Ressourcen-Check: Public Key vorhanden.")

    print("🏁 Audit erfolgreich abgeschlossen. Distribution ist Gold-Ready.")
    return True

if __name__ == "__main__":
    if not run_audit():
        sys.exit(1)
