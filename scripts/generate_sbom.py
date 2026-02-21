#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _pip_freeze() -> list[dict[str, str]]:
    result = _run([sys.executable, "-m", "pip", "freeze"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pip freeze failed")
    packages: list[dict[str, str]] = []
    for raw in (result.stdout or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
        else:
            name, version = line, ""
        packages.append({"name": name.strip(), "version": version.strip()})
    return sorted(packages, key=lambda item: item["name"].lower())


def _run_pip_audit() -> dict[str, Any]:
    if shutil.which("pip-audit") is None:
        return {"status": "not_available", "command": "pip-audit"}
    result = _run(["pip-audit", "-f", "json"])
    payload: dict[str, Any] = {
        "status": "ok" if result.returncode == 0 else "issues_found_or_error",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lightweight SBOM and scan metadata.")
    parser.add_argument("--out", type=str, default="output/sbom/sbom.json")
    parser.add_argument("--with-pip-audit", action="store_true")
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    packages = _pip_freeze()
    payload: dict[str, Any] = {
        "schema": "kukanilea.sbom.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": "scripts/generate_sbom.py",
        "python": sys.version,
        "package_count": len(packages),
        "packages": packages,
    }

    if args.with_pip_audit:
        payload["pip_audit"] = _run_pip_audit()

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
