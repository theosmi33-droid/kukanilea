#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _subjects(artifacts_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not artifacts_dir.exists():
        return out
    for path in sorted(artifacts_dir.rglob("*")):
        if not path.is_file():
            continue
        out.append(
            {
                "name": path.name,
                "uri": str(path),
                "digest": {"sha256": _sha256(path)},
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SLSA-style build provenance skeleton.")
    parser.add_argument("--artifacts-dir", type=str, default="dist")
    parser.add_argument("--out", type=str, default="output/provenance/provenance.json")
    parser.add_argument("--builder-id", type=str, default="kukanilea.local/builder")
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": _subjects(artifacts_dir),
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "kukanilea.release",
                "externalParameters": {
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                },
                "internalParameters": {},
                "resolvedDependencies": [],
            },
            "runDetails": {
                "builder": {"id": args.builder_id},
                "metadata": {
                    "invocationId": os.environ.get("GITHUB_RUN_ID") or datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
                    "startedOn": datetime.now(UTC).isoformat(),
                    "finishedOn": datetime.now(UTC).isoformat(),
                },
            },
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
