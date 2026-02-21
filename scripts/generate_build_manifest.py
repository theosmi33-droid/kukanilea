#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_files(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if not root.exists():
        return files
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        files.append(
            {
                "path": rel,
                "size_bytes": p.stat().st_size,
                "sha256": _sha256(p),
            }
        )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic build hash manifest.")
    parser.add_argument("--input-dir", type=str, default="dist")
    parser.add_argument("--out", type=str, default="output/build/manifest.json")
    args = parser.parse_args()

    src = Path(args.input_dir).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    files = _collect_files(src)
    payload = {
        "schema": "kukanilea.build-manifest.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "input_dir": str(src),
        "file_count": len(files),
        "files": files,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
