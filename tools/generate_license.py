#!/usr/bin/env python3
"""Generate a signed tenant license JSON.

Requires: pip install pynacl
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date

from nacl.signing import SigningKey


def sign_license(private_key_hex: str, payload: dict) -> dict:
    signer = SigningKey(bytes.fromhex(private_key_hex))
    message = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = signer.sign(message).signature
    payload["signature"] = signature.hex()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--hw", required=True, help="device hw fingerprint")
    parser.add_argument("--valid-until", default=str(date(2030, 1, 1)))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    private_hex = os.environ.get("KUKANILEA_LICENSE_PRIV")
    if not private_hex:
        raise SystemExit("Set KUKANILEA_LICENSE_PRIV (hex) in env")

    payload = {
        "tenant_id": args.tenant,
        "hw_fingerprint": args.hw,
        "valid_until": args.valid_until,
        "issued_at": str(date.today()),
        "flags": {"trial": False},
    }

    signed = sign_license(private_hex, payload)
    out_path = args.out or f"{args.tenant}_license.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(signed, fh, ensure_ascii=False, indent=2)

    print("Wrote", out_path)


if __name__ == "__main__":
    main()
