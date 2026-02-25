"""
scripts/tests/test_remote_license.py
Automatisierter Test für die Remote-Lizenz-Validierung via Excel.
"""
import os
import sys
import time
import subprocess
import pandas as pd
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.core.license_manager import license_manager

EXCEL_PATH = "license_server/licenses.xlsx"
SERVER_URL = "http://127.0.0.1:9090"

def update_excel(hwid: str, is_active: bool):
    print(f"📝 Update Excel: Setze HWID '{hwid}' auf Active={is_active}")
    if os.path.exists(EXCEL_PATH):
        df = pd.read_excel(EXCEL_PATH)
        df['HardwareID'] = df['HardwareID'].astype(str)
    else:
        df = pd.DataFrame(columns=["HardwareID", "CustomerName", "Plan", "ValidUntil", "IsActive"])
        
    if hwid in df['HardwareID'].values:
        df.loc[df['HardwareID'] == hwid, 'IsActive'] = is_active
    else:
        new_row = pd.DataFrame([{
            "HardwareID": hwid,
            "CustomerName": "Automated Test Node",
            "Plan": "GOLD",
            "ValidUntil": "2030-12-31",
            "IsActive": is_active
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        
    df.to_excel(EXCEL_PATH, index=False)

def run_test():
    print("")
    print("--- KUKANILEA EXCEL-LICENSE-CONTROL TEST ---")
    
    hwid = license_manager.hardware_id
    print(f"Lokale Hardware-ID: {hwid}")
    
    os.makedirs("license_server", exist_ok=True)
    update_excel(hwid, True)
    
    print("🚀 Starte lokalen Lizenz-Server (Port 9090)...")
    server_proc = subprocess.Popen(
        [sys.executable, "license_server/server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd="."
    )
    time.sleep(2)
    
    try:
        from app.config import Config
        Config.TESTING = False # Zwinge echte Prüfung
        Config.LICENSE_VALIDATE_URL = f"{SERVER_URL}/api/v1/license/validate"
        
        # Bypass lokale Signaturprüfung für diesen Architekturtest
        license_manager._license_data = {"simulated": "local_valid"}
        
        # 1. Test: Aktiv
        print("🔍 Test 1: Überprüfe GÜLTIGE Lizenz (in Excel)")
        if hasattr(license_manager, "_remote_check_cache"):
            delattr(license_manager, "_remote_check_cache")
        
        result_active = license_manager.is_valid()
        print(f"Ergebnis: {'✅ ERLAUBT' if result_active else '❌ BLOCKIERT'}")
        
        # 2. Test: Revoked (in Excel ändern)
        update_excel(hwid, False)
        
        print("🔍 Test 2: Überprüfe ENTZOGENE Lizenz (in Excel)")
        if hasattr(license_manager, "_remote_check_cache"):
            delattr(license_manager, "_remote_check_cache")
            
        result_revoked = license_manager.is_valid()
        print(f"Ergebnis: {'✅ ERLAUBT' if result_revoked else '❌ BLOCKIERT'}")
        
        if result_active and not result_revoked:
            print("🏆 TEST BESTANDEN: Excel-basierte Remote-Steuerung funktioniert!")
        else:
            print("⚠️ FEHLER: Umschaltung nicht erfolgreich.")
            sys.exit(1)
            
    finally:
        print("🛑 Beende Lizenz-Server...")
        server_proc.terminate()
        server_proc.wait()

if __name__ == "__main__":
    run_test()
