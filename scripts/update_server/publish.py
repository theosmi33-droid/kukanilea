#!/usr/bin/env python3
"""
scripts/update_server/publish.py
Signiert ein KUKANILEA Update-Archiv (ZIP) und generiert ein `manifest.json`.
"""

import sys
import json
import base64
import argparse
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

def publish_update():
    parser = argparse.ArgumentParser(description="KUKANILEA Update Publisher (RSA Signatures)")
    parser.add_argument("--version", required=True, help="Release Version (z.B. v1.5.1-gold)")
    parser.add_argument("--archive", required=True, help="Pfad zum .zip Update-Archiv")
    parser.add_argument("--platform", default="mac", help="Zielplattform (mac, win, linux)")
    parser.add_argument("--outdir", default="updates", help="Output Verzeichnis für Manifest und Archiv")
    
    args = parser.parse_args()
    
    priv_path = Path("internal_vault/license_priv.pem")
    if not priv_path.exists():
        print("[ERROR] Fehler: Private Key nicht gefunden (internal_vault/license_priv.pem).")
        sys.exit(1)

    archive_path = Path(args.archive)
    if not archive_path.exists():
        print(f"[ERROR] Fehler: Update-Archiv {args.archive} existiert nicht.")
        sys.exit(1)

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. SHA256 des Archivs berechnen
    print(f"Berechne SHA256 für {archive_path.name}...")
    file_sha256 = compute_sha256(archive_path)

    # 2. Manifest Payload erstellen (Ohne Signaturen)
    # Beachte: Die Client-Logik in app/update.py löscht "signatures", "signature", 
    # "signature_alg" und "signature_key_id" vor der Hash-Berechnung.
    payload = {
        "version": args.version,
        "release_url": "https://deine-domain.com/updates", # Dummy oder Info URL
        "published_at": datetime.now(timezone.utc).isoformat(),
        "assets": [
            {
                "name": archive_path.name,
                "platform": args.platform,
                # Die URL wird vom Client aus dem Manifest_URL abgeleitet oder fest hinterlegt, 
                # hier ein relativer Pfad
                "url": f"{archive_path.name}", 
                "sha256": file_sha256
            }
        ]
    }
    
    # Kanonisches JSON erzeugen (wie im Client: separators=(',', ':'), sort_keys=True)
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    payload_bytes = payload_json.encode('utf-8')
    
    # 3. Payload signieren (RSA-PSS mit SHA256)
    password = os.environ.get("KUKANILEA_VAULT_PASS", "kukanilea-gold-safe-2026").encode()
    with open(priv_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(key_file.read(), password=password)
        
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    # 4. Signatur zum Manifest hinzufügen (als Base64)
    sig_b64 = base64.b64encode(signature).decode('utf-8')
    
    manifest_data = dict(payload)
    manifest_data["signature"] = sig_b64
    manifest_data["signature_alg"] = "RSA-PSS-SHA256"
    manifest_data["signature_key_id"] = "kukanilea-master-key"
    
    manifest_path = out_dir / "manifest.json"
    
    with open(manifest_path, "w") as f:
        # Hier formatieren wir schön für Lesbarkeit, der Client normalisiert ohnehin
        json.dump(manifest_data, f, indent=2)
        
    # Kopiere das Archiv in das Output-Verzeichnis
    target_archive = out_dir / archive_path.name
    if archive_path != target_archive:
        import shutil
        shutil.copy2(archive_path, target_archive)
        
    print(f"[SUCCESS] Update Manifest erfolgreich signiert und generiert: {manifest_path}")
    print(f"   Archiv SHA256: {file_sha256}")
    
    # Optional: NAS Spiegelung
    nas_path = Path("/KUKANILEA-ENDKUNDE")
    volumes_nas = Path("/Volumes/KUKANILEA-ENDKUNDE")
    
    sync_dir = None
    if nas_path.exists(): sync_dir = nas_path
    elif volumes_nas.exists(): sync_dir = volumes_nas
    
    if sync_dir:
        update_nas_dir = sync_dir / "updates"
        update_nas_dir.mkdir(exist_ok=True)
        shutil.copy2(manifest_path, update_nas_dir / "manifest.json")
        shutil.copy2(target_archive, update_nas_dir / target_archive.name)
        print(f"📡 Update erfolgreich auf NAS gespiegelt: {update_nas_dir}")

if __name__ == "__main__":
    publish_update()
