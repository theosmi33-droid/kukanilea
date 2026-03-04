#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a CI gate report artifact.")
    parser.add_argument("--name", required=True, help="Gate/corridor name")
    parser.add_argument("--status", required=True, choices=["pass", "fail"])
    parser.add_argument("--command", required=True, help="Executed command")
    parser.add_argument("--output", default="ci-report.json", help="Output path")
    args = parser.parse_args()

    payload = {
        "name": args.name,
        "status": args.status,
        "command": args.command,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
