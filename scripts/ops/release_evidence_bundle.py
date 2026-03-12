#!/usr/bin/env python3
"""Build a small reproducible release-evidence bundle for current main.

The bundle focuses on:
- Guardrails
- Healthcheck
- Targeted release/security tests
- Security gate + packaging fingerprints
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TESTS = [
    "tests/security/test_verify_guardrails.py",
    "tests/test_release_validator.py",
]
PACKAGING_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "requirements.lock",
    "package.json",
    "package-lock.json",
]


@dataclass
class CheckResult:
    name: str
    command: str
    status: str
    exit_code: int
    log_file: str


def _run_check(name: str, command: Sequence[str], logs_dir: Path) -> CheckResult:
    log_path = logs_dir / f"{name.lower().replace(' ', '_')}.log"
    with log_path.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
    return CheckResult(
        name=name,
        command=" ".join(shlex.quote(part) for part in command),
        status="PASS" if proc.returncode == 0 else "FAIL",
        exit_code=proc.returncode,
        log_file=str(log_path.relative_to(ROOT)),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 128), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _git_value(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def build_bundle(output_dir: Path, tests: Sequence[str]) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / ts
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    python_bin = os.environ.get("PYTHON") or str(ROOT / ".venv" / "bin" / "python")
    if not Path(python_bin).exists():
        python_bin = "python3"

    checks = [
        _run_check("guardrails", [python_bin, "scripts/ops/verify_guardrails.py"], logs_dir),
        _run_check("healthcheck", ["bash", "scripts/ops/healthcheck.sh", "--skip-pytest"], logs_dir),
        _run_check("relevant_tests", [python_bin, "-m", "pytest", "-q", *tests], logs_dir),
        _run_check("security_gate", ["bash", "scripts/ops/security_gate.sh"], logs_dir),
    ]

    packaging = []
    for rel in PACKAGING_FILES:
        path = ROOT / rel
        if path.exists():
            packaging.append({
                "file": rel,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            })

    payload = {
        "timestamp_utc": ts,
        "git": {
            "branch": _git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "commit": _git_value("rev-parse", "HEAD"),
            "status_short": _git_value("status", "--short", "--branch"),
        },
        "checks": [asdict(c) for c in checks],
        "packaging_evidence": packaging,
        "overall_status": "PASS" if all(c.status == "PASS" for c in checks) else "FAIL",
    }

    json_path = run_dir / "release_evidence.json"
    md_path = run_dir / "release_evidence.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Release Evidence Bundle",
        "",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        f"- Branch: `{payload['git']['branch']}`",
        f"- Commit: `{payload['git']['commit']}`",
        f"- Overall status: **{payload['overall_status']}**",
        "",
        "## Check Matrix",
        "",
        "| Check | Status | Exit | Command | Log |",
        "|---|---|---:|---|---|",
    ]
    for check in payload["checks"]:
        lines.append(
            f"| {check['name']} | {check['status']} | {check['exit_code']} | `{check['command']}` | `{check['log_file']}` |"
        )

    lines.extend(["", "## Packaging Evidence", "", "| File | SHA256 | Size (bytes) |", "|---|---|---:|"])
    for item in packaging:
        lines.append(f"| `{item['file']}` | `{item['sha256']}` | {item['size_bytes']} |")

    lines.extend(["", "## Git Status Snapshot", "", "```", payload["git"]["status_short"], "```", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    latest_json = output_dir / "release_evidence_latest.json"
    latest_md = output_dir / "release_evidence_latest.md"
    latest_json.write_text(_read_text(json_path), encoding="utf-8")
    latest_md.write_text(_read_text(md_path), encoding="utf-8")

    return {
        "json": str(json_path.relative_to(ROOT)),
        "markdown": str(md_path.relative_to(ROOT)),
        "latest_json": str(latest_json.relative_to(ROOT)),
        "latest_markdown": str(latest_md.relative_to(ROOT)),
        "overall_status": payload["overall_status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create reproducible release evidence bundle")
    parser.add_argument("--output-dir", default="docs/status/release_evidence", help="output directory")
    parser.add_argument("--test", action="append", dest="tests", default=[], help="additional relevant test path")
    args = parser.parse_args()

    tests = args.tests or DEFAULT_TESTS
    result = build_bundle(ROOT / args.output_dir, tests)
    print(json.dumps(result, indent=2))
    return 0 if result["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
