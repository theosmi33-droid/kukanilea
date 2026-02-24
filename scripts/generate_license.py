#!/usr/bin/env python3
"""
Lizenzgenerator für KUKANILEA (Admins/Release Management).
Erzeugt eine RSA-signierte license.bin auf Basis der Hardware-ID.
"""

import sys
import json
import argparse
import os
import uuid
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PrivateFormat, NoEncryption, PublicFormat

def get_private_key(key_path: Path):
    env_key_b64 = os.environ.get("KUKANILEA_LICENSE_PRIV")
    if env_key_b64:
        try:
            pem_data = base64.b64decode(env_key_b64)
            return load_pem_private_key(pem_data, password=None)
        except Exception as e:
            print(f"Fehler beim Laden des Schlüssels aus Umgebungsvariable: {e}")
            sys.exit(1)
            
    if key_path and key_path.exists():
        with open(key_path, "rb") as key_file:
            return load_pem_private_key(key_file.read(), password=None)
            
    print("Fehler: Kein Private Key in Umgebungsvariable KUKANILEA_LICENSE_PRIV oder Datei gefunden.")
    sys.exit(1)

def generate_license(hardware_id: str, days: int, private_key_path: Path, output_path: Path):
    private_key = get_private_key(private_key_path)

    expiry_date = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    payload = {
        "hardware_id": hardware_id,
        "type": "gold",
        "features": ["all"],
        "version": "1.5.0-gold",
        "expiry_date": expiry_date
    }

    payload_str = json.dumps(payload, sort_keys=True)
    payload_bytes = payload_str.encode('utf-8')

    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    license_data = {
        "signature": signature.hex(),
        "payload": payload
    }

    with open(output_path, "w") as out_file:
        json.dump(license_data, out_file, indent=2)

    print(f"✅ Lizenz erfolgreich generiert für Hardware-ID: {hardware_id}")
    print(f"   Ablaufdatum: {expiry_date}")
    print(f"💾 Gespeichert unter: {output_path}")

def generate_keys(private_key_path: Path, public_key_path: Path):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    with open(private_key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption()
        ))
        
    public_key = private_key.public_key()
    with open(public_key_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        ))
    print(f"✅ Schlüsselpaar generiert: {private_key_path} / {public_key_path}")
    print(f"Tipp: Exportiere den Private Key als Base64 für CI/CD:")
    print(f"base64 -i {private_key_path} | tr -d '\n'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KUKANILEA Lizenz-Generator")
    parser.add_argument("--hwid", help="Hardware-ID (MAC-Hex)", required=False)
    parser.add_argument("--days", type=int, default=365, help="Gültigkeitsdauer in Tagen")
    parser.add_argument("--out", default="license.bin", help="Output Pfad")
    parser.add_argument("--key", default="private_key.pem", help="Pfad zum Private Key")
    parser.add_argument("--gen-keys", action="store_true", help="Erzeuge ein neues Schlüsselpaar")
    
    args = parser.parse_args()
    
    if args.gen_keys:
        generate_keys(Path(args.key), Path("public_key.pem"))
        sys.exit(0)
        
    if not args.hwid:
        mac = uuid.getnode()
        args.hwid = f"{mac:012x}"
        print(f"Keine --hwid angegeben, nutze lokale Hardware-ID: {args.hwid}")

    generate_license(args.hwid, args.days, Path(args.key), Path(args.out))
