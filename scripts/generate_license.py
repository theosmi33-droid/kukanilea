#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import uuid
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PUBLIC_KEY_HEX = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"


def canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def device_fingerprint() -> str:
    raw = f"{uuid.getnode()}::{socket.gethostname()}".encode()
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate signed offline KUKANILEA license"
    )
    parser.add_argument("--customer", required=True, help="Customer identifier")
    parser.add_argument(
        "--plan",
        required=True,
        choices=["PRO", "ENTERPRISE"],
        help="License plan",
    )
    parser.add_argument(
        "--days", type=int, required=True, help="License validity in days"
    )
    parser.add_argument(
        "--bind-device",
        action="store_true",
        help="Bind license to current device fingerprint",
    )
    parser.add_argument(
        "--out",
        default="license.json",
        help="Output file path (default: license.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    priv_hex = os.environ.get("KUKANILEA_LICENSE_PRIV", "").strip()
    if not priv_hex:
        raise SystemExit("KUKANILEA_LICENSE_PRIV is required (hex private key)")

    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    public_hex = private_key.public_key().public_bytes_raw().hex()
    if public_hex != PUBLIC_KEY_HEX:
        raise SystemExit("Provided private key does not match embedded PUBLIC_KEY_HEX")

    issued = date.today()
    expiry = issued + timedelta(days=max(1, args.days))
    payload = {
        "customer_id": args.customer,
        "plan": args.plan,
        "issued": issued.isoformat(),
        "expiry": expiry.isoformat(),
    }
    if args.bind_device:
        payload["device_fingerprint"] = device_fingerprint()

    signature = private_key.sign(canonical_payload_bytes(payload))
    payload["signature"] = base64.b64encode(signature).decode("ascii")

    out = Path(args.out).resolve()
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"license_written={out}")


if __name__ == "__main__":
    main()
