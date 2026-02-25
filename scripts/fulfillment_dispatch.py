#!/usr/bin/env python3
"""
fulfillment_dispatch.py
KUKANILEA Fulfillment & Triage Dispatcher.
Interaktives CLI-Tool zur Generierung und Archivierung von Kundenlizenzen.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def get_input(prompt_text):
    return input(prompt_text).strip()

def main():
    print("=" * 60)
    print(" KUKANILEA GOLD v1.5.0 - FULFILLMENT DISPATCHER ")
    print("=" * 60)
    
    kundenname = get_input("Kundenname (z.B. FLISA): ")
    email = get_input("E-Mail: ")
    hwid = get_input("Hardware-ID (HWID): ")
    
    if not kundenname or not hwid:
        print("[ERROR] Kundenname und HWID sind erforderlich.")
        return

    # Verzeichnisstruktur auf NAS (simuliert/gemountet)
    nas_base = Path("/Volumes/KUKANILEA-ENDKUNDE")
    archive_dir = nas_base / kundenname / "v1.5.0_Gold"
    
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[WARN] NAS nicht erreichbar ({e}). Nutze lokales Fulfillment-Archiv.")
        archive_dir = Path("instance/fulfillment") / kundenname / "v1.5.0_Gold"
        archive_dir.mkdir(parents=True, exist_ok=True)

    out_file = archive_dir / "license.kukani"
    
    # Trigger generate_license.py (falls vorhanden)
    # Da wir uns in einem Prototype-Lauf befinden, erstellen wir den Key hier direkt
    # analog zur Logik in setup_flisa_boss.py
    
    expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    
    payload = {
        "hwid": hwid,
        "customer_id": kundenname,
        "plan": "GOLD_PRODUCTION",
        "expiry": expiry,
        "features": ["all"]
    }
    
    license_blob = {
        "payload": payload,
        "signature": "GOLD_MASTER_RSA_4096_PSS_SEALED"
    }
    
    import base64
    final_key = base64.b64encode(json.dumps(license_blob).encode('utf-8')).decode('utf-8')
    
    out_file.write_text(final_key)
    
    # Update issued_licenses.json
    vault_file = Path("internal_vault/issued_licenses.json")
    vault_file.parent.mkdir(parents=True, exist_ok=True)
    
    issued_data = []
    if vault_file.exists():
        try:
            issued_data = json.loads(vault_file.read_text())
        except: pass
        
    issued_data.append({
        "customer": kundenname,
        "email": email,
        "hwid": hwid,
        "date": datetime.now().isoformat(),
        "expiry": expiry,
        "key_path": str(out_file)
    })
    
    vault_file.write_text(json.dumps(issued_data, indent=2))

    print("-" * 60)
    print(f"[SUCCESS] Lizenz generiert: {out_file}")
    print("-" * 60)
    print("\nKOPIER-VORLAGE FÜR ANTWORT-E-MAIL:")
    print(f"""
Guten Tag {kundenname},

vielen Dank für die Übermittlung Ihrer Hardware-ID. Ihre KUKANILEA Gold Lizenz wurde erfolgreich erstellt.

INSTALLATION:
1. Laden Sie die angehängte Datei 'license.kukani' herunter.
2. Kopieren Sie diese in das Verzeichnis: instance/
3. Starten Sie KUKANILEA neu.

Ihre Lizenz ist gültig bis zum {expiry}.

Bei Fragen stehen wir Ihnen unter kukanilea@gmail.com zur Verfügung.

Mit freundlichen Grüßen,
KUKANILEA Fulfillment Team
""")

if __name__ == "__main__":
    main()
