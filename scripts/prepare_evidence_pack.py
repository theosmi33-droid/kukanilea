#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SECTIONS = [
    "security",
    "e2e",
    "perf",
    "distribution",
    "update",
    "sbom",
    "provenance",
    "compliance",
]


DEFAULT_FILES = {
    "security": ["REPORT_HARDENING_SECURITY.md", "REPORT_SECURITY_CHECKS.md"],
    "e2e": ["REPORT_HARDENING_E2E.md", "REPORT_HARDENING_UX.md"],
    "perf": ["REPORT_HARDENING_PERF.md", "REPORT_RC_ENDURANCE_60M.md"],
    "distribution": [
        "REPORT_HARDENING_DISTRIBUTION.md",
        "REPORT_RC_DISTRIBUTION_MACOS.md",
        "REPORT_RC_DISTRIBUTION_WINDOWS.md",
    ],
    "update": ["REPORT_HARDENING_UPDATE_ROLLBACK.md"],
    "sbom": ["REPORT_SBOM.md"],
    "provenance": ["REPORT_PROVENANCE.md"],
    "compliance": [
        "docs/RELEASE_GATES.md",
        "docs/COMPLIANCE_EU_DE_FOR_FEATURES.md",
        "docs/CRA_READINESS.md",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare release evidence pack folder structure.")
    parser.add_argument("--version", required=True, help="Release identifier, e.g. v1.0.0-rc1")
    parser.add_argument("--root", default="evidence", help="Evidence root folder")
    parser.add_argument("--copy-defaults", action="store_true", help="Copy known report files when present")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    pack_root = (project_root / args.root / args.version).resolve()
    pack_root.mkdir(parents=True, exist_ok=True)

    for section in SECTIONS:
        section_dir = pack_root / section
        section_dir.mkdir(parents=True, exist_ok=True)
        if args.copy_defaults:
            for rel in DEFAULT_FILES.get(section, []):
                src = (project_root / rel).resolve()
                if src.exists() and src.is_file():
                    shutil.copy2(src, section_dir / src.name)

    print(str(pack_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
