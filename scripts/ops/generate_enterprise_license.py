import base64
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    print("Error: 'cryptography' library required. Run 'pip install cryptography'.")
    sys.exit(1)

PRIVATE_KEY_PATH = Path("instance/kukanilea_private.key")


def ensure_private_key():
    if not PRIVATE_KEY_PATH.exists():
        print("Generating new Master Private Key...")
        private_key = Ed25519PrivateKey.generate()
        PRIVATE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.OpenSSH,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        print(f"Master Key saved to {PRIVATE_KEY_PATH}. KEEP THIS SAFE!")

        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        print(f"PUBLIC KEY HEX: {pub_bytes.hex()}")
        return private_key
    else:
        with open(PRIVATE_KEY_PATH, "rb") as f:
            return serialization.load_ssh_private_key(f.read(), password=None)


def generate_license(
    hwid: str, customer_name: str, days: int = 365, plan: str = "ENTERPRISE"
):
    private_key = ensure_private_key()

    expiry = (date.today() + timedelta(days=days)).isoformat()
    payload = {
        "customer": customer_name,
        "device_fingerprint": hwid.replace("KUK-", "").replace("-", ""),
        "expiry": expiry,
        "plan": plan,
        "issued_at": date.today().isoformat(),
    }

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    signature = private_key.sign(payload_bytes)
    payload["signature"] = base64.b64encode(signature).decode("utf-8")

    license_file = Path(f"license_{customer_name.replace(' ', '_')}.json")
    with open(license_file, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\n[SUCCESS] License generated for {customer_name}")
    print(f"File: {license_file}")
    print(f"Valid until: {expiry}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_enterprise_license.py <HWID> <CustomerName>")
        ensure_private_key()
    else:
        generate_license(sys.argv[1], sys.argv[2])
