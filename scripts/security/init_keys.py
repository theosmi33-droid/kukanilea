"""
scripts/security/init_keys.py
Generiert das KUKANILEA RSA-Master-Schlüsselpaar für die v1.5.0 Gold Edition.
"""
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def init_vault():
    vault_dir = Path("internal_vault")
    cert_dir = Path("app/core/certs")
    
    vault_dir.mkdir(exist_ok=True)
    cert_dir.mkdir(parents=True, exist_ok=True)
    
    priv_path = vault_dir / "license_priv.pem"
    pub_path = cert_dir / "license_pub.pem"
    
    if priv_path.exists():
        print("[WARNING]  Master-Keys existieren bereits. Abbruch aus Sicherheitsgründen.")
        return

    print("🔐 Generiere 4096-bit RSA Schlüsselpaar...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096
    )
    
    # Speichere Private Key (Verschlüsselt)
    password = os.environ.get("KUKANILEA_VAULT_PASS", "kukanilea-gold-safe-2026").encode()
    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password)
        ))
        
    # Speichere Public Key (Unverschlüsselt für Distribution)
    public_key = private_key.public_key()
    with open(pub_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
        
    print(f"[SUCCESS] Master-Keys erfolgreich erstellt.")
    print(f"   Vault: {priv_path}")
    print(f"   Certs: {pub_path}")

if __name__ == "__main__":
    init_vault()
