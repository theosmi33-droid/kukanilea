#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and sign KUKANILEA update manifest."
    )
    parser.add_argument(
        "--version", required=True, help="Release version, e.g. 1.0.0-beta.3"
    )
    parser.add_argument("--release-url", default="", help="Optional release URL")
    parser.add_argument(
        "--assets-json",
        required=True,
        help="Path to JSON array of assets [{name,platform,url,sha256}]",
    )
    parser.add_argument(
        "--private-key-file",
        required=True,
        help="Path to Ed25519 private key in PEM format",
    )
    parser.add_argument("--key-id", default="release-main", help="Signing key ID")
    parser.add_argument("--output", required=True, help="Output manifest JSON path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    assets_path = Path(args.assets_json).expanduser().resolve()
    key_path = Path(args.private_key_file).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    if not isinstance(assets, list):
        raise SystemExit("assets-json must be a JSON array")

    private_key = serialization.load_pem_private_key(
        key_path.read_bytes(),
        password=None,
    )
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise SystemExit("private key must be Ed25519")

    payload = {
        "version": str(args.version).strip(),
        "release_url": str(args.release_url or "").strip(),
        "generated_at": _now_iso(),
        "assets": assets,
    }
    signature = private_key.sign(_canonical_json_bytes(payload))
    signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    manifest = {
        **payload,
        "signatures": [
            {
                "alg": "ed25519",
                "key_id": str(args.key_id or "").strip(),
                "sig": signature_b64,
            }
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
