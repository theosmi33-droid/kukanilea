#!/usr/bin/env python3
"""Validate that release healthcheck and CI checks stay aligned."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HEALTHCHECK = ROOT / "scripts" / "ops" / "healthcheck.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def main() -> int:
    missing: list[str] = []

    health_src = HEALTHCHECK.read_text(encoding="utf-8")
    ci_src = CI_WORKFLOW.read_text(encoding="utf-8")

    health_markers = [
        "Python compile check",
        "ensure_agent_memory.py",
        "pytest -q",
        "verify_guardrails.py",
    ]

    ci_markers = [
        "scripts/ops/healthcheck.sh --ci",
        "pytest -q tests --ignore=tests/e2e",
    ]

    for marker in health_markers:
        if marker not in health_src:
            missing.append(f"healthcheck marker missing: {marker}")

    for marker in ci_markers:
        if marker not in ci_src:
            missing.append(f"ci workflow marker missing: {marker}")

    if missing:
        print("[ci-alignment] FAIL")
        for item in missing:
            print(f"- {item}")
        return 1

    print("[ci-alignment] PASS")
    print(f"- healthcheck: {HEALTHCHECK.relative_to(ROOT)}")
    print(f"- workflow: {CI_WORKFLOW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
