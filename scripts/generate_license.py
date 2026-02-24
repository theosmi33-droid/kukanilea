"""
scripts/generate_license.py
Internes Tool zur Generierung RSA-signierter Lizenzen.
Bindet Features und Ablaufdatum an die Hardware-ID.
"""
import sys
import json
import base64
import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

def generate():
    parser = argparse.ArgumentParser(description="KUKANILEA RSA License Generator")
    parser.add_argument("--hwid", required=True, help="Hardware-ID des Kunden")
    parser.add_argument("--days", type=int, default=365, help="Gültigkeitsdauer")
    parser.add_argument("--features", default="vision_pro,voice_extra", help="JSON oder Komma-Liste")
    parser.add_argument("--out", default="license.kukani", help="Zielpfad")
    
    args = parser.parse_args()
    
    priv_path = Path("internal_vault/license_priv.pem")
    if not priv_path.exists():
        print("❌ Fehler: Vault nicht initialisiert.")
        return

    # Payload vorbereiten
    expiry = (datetime.now(timezone.utc) + timedelta(days=args.days)).isoformat()
    features = [f.strip() for f in args.features.split(",")]
    
    payload = {
        "hwid": args.hwid,
        "expiry": expiry,
        "features": features,
        "edition": "Gold v1.5.0",
        "issued_at": datetime.now(timezone.utc).isoformat()
    }
    
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    
    # Signieren
    password = os.environ.get("KUKANILEA_VAULT_PASS", "kukanilea-gold-safe-2026").encode()
    with open(priv_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=password)
        
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    # Paketieren (Base64 Bundle)
    bundle = {
        "payload": payload,
        "signature": signature.hex()
    }
    
    key_string = base64.b64encode(json.dumps(bundle).encode('utf-8')).decode('utf-8')
    
    # Lokale Speicherung
    with open(args.out, "w") as f:
        f.write(key_string)
        
    # NAS-Spiegelung (Falls gemountet)
    nas_path = Path("/KUKANILEA-ENDKUNDE")
    if nas_path.exists():
        customer_dir = nas_path / args.hwid
        customer_dir.mkdir(parents=True, exist_ok=True)
        nas_file = customer_dir / f"license_{datetime.now(timezone.utc).strftime('%Y%m%d')}.kukani"
        nas_file.write_text(key_string)
        print(f"📡 NAS-Spiegelung erfolgreich: {nas_file}")
    else:
        # Fallback für macOS SMB Mountpoint-Check falls Root-Mount nicht da
        volumes_nas = Path("/Volumes/KUKANILEA-ENDKUNDE")
        if volumes_nas.exists():
            customer_dir = volumes_nas / args.hwid
            customer_dir.mkdir(parents=True, exist_ok=True)
            nas_file = customer_dir / f"license_{datetime.now(timezone.utc).strftime('%Y%m%d')}.kukani"
            nas_file.write_text(key_string)
            print(f"📡 NAS-Spiegelung (/Volumes) erfolgreich: {nas_file}")
        else:
            print("ℹ️ NAS /KUKANILEA-ENDKUNDE nicht gemountet. Nur lokale Kopie erstellt.")
        
    print(f"✅ Lizenz für {args.hwid} generiert. Ablauf: {expiry}")
    print(f"💾 Datei: {args.out}")

if __name__ == "__main__":
    generate()
