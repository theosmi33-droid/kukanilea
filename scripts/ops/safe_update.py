#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from app.core.inplace_update import InPlaceUpdater, UpdateError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KUKANILEA safe in-place update runner")
    parser.add_argument("--install-root", required=True, help="Install root path")
    parser.add_argument("--data-dir", required=True, help="Persistent data directory")
    parser.add_argument("--version", required=True, help="Release version")

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--source-dir", help="Prepared release directory")
    src.add_argument("--tarball", help="Tarball payload")

    parser.add_argument(
        "--healthcheck-cmd",
        default="",
        help="Healthcheck command executed in new release directory",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Optional signed manifest path for verification",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    updater = InPlaceUpdater(Path(args.install_root), Path(args.data_dir))

    healthcheck = shlex.split(args.healthcheck_cmd) if args.healthcheck_cmd else None
    manifest = Path(args.manifest) if args.manifest else None

    try:
        if args.source_dir:
            result = updater.apply_from_directory(
                Path(args.source_dir),
                args.version,
                healthcheck_cmd=healthcheck,
                manifest_path=manifest,
            )
        else:
            result = updater.apply_from_tarball(
                Path(args.tarball),
                args.version,
                healthcheck_cmd=healthcheck,
                manifest_path=manifest,
            )
    except UpdateError as exc:
        print(f"UPDATE FAILED: {exc}")
        return 1

    print(f"UPDATE OK: version={result.version}")
    print(f"release={result.release_dir}")
    print(f"previous={result.previous_release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
