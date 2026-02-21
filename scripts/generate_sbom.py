#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
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


def _to_cyclonedx(packages: list[dict[str, str]]) -> dict[str, Any]:
    serial = f"urn:uuid:{uuid.uuid4()}"
    components: list[dict[str, Any]] = []
    for item in packages:
        name = item["name"]
        version = item["version"] or "unknown"
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "tools": [
                {
                    "vendor": "kukanilea",
                    "name": "scripts/generate_sbom.py",
                    "version": "1.0",
                }
            ],
            "component": {"type": "application", "name": "kukanilea"},
        },
        "components": components,
    }


def _to_spdx(packages: list[dict[str, str]]) -> dict[str, Any]:
    document_namespace = f"https://kukanilea.local/spdx/{uuid.uuid4()}"
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    spdx_packages: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = []
    for item in packages:
        name = item["name"]
        version = item["version"] or "unknown"
        spdx_id = f"SPDXRef-Package-{name.replace('.', '-').replace('_', '-')}"
        spdx_packages.append(
            {
                "name": name,
                "SPDXID": spdx_id,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": spdx_id,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "kukanilea-sbom",
        "documentNamespace": document_namespace,
        "creationInfo": {
            "created": now,
            "creators": ["Tool: scripts/generate_sbom.py"],
        },
        "packages": spdx_packages,
        "relationships": relationships,
    }


def _to_internal(packages: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": "kukanilea.sbom.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": "scripts/generate_sbom.py",
        "python": sys.version,
        "package_count": len(packages),
        "packages": packages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate lightweight SBOM and scan metadata.")
    parser.add_argument("--out", type=str, default="output/sbom/sbom.json")
    parser.add_argument("--with-pip-audit", action="store_true")
    parser.add_argument(
        "--format",
        choices=["cyclonedx", "spdx", "internal"],
        default="cyclonedx",
        help="Output schema flavor.",
    )
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    packages = _pip_freeze()
    if args.format == "spdx":
        payload = _to_spdx(packages)
    elif args.format == "internal":
        payload = _to_internal(packages)
    else:
        payload = _to_cyclonedx(packages)

    if args.with_pip_audit:
        payload["pip_audit"] = _run_pip_audit()

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
