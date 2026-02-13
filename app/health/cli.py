#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.health import checks
from app.health.core import HealthRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["ci", "runtime"], default="ci")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", dest="json_out")
    parser.add_argument("--eventlog-limit", type=int, default=200)
    parser.add_argument("--timeout-s", type=float, default=2.0)
    args = parser.parse_args()

    runner = HealthRunner(
        mode=args.mode,
        strict=args.strict,
        eventlog_limit=args.eventlog_limit,
        timeout_s=args.timeout_s,
    )
    runner.checks = [getattr(checks, name) for name in checks.ALL_CHECKS]

    report = runner.run()
    for chk in report.checks:
        status = "✅" if chk.ok else "❌" if chk.severity == "fail" else "⚠️"
        print(f"{status} {chk.name}: {chk.reason or ''}")
        if chk.remediation:
            print(f"    remediation: {chk.remediation}")

    data = {
        "ts": report.ts.isoformat(),
        "mode": report.mode,
        "ok": report.ok,
        "checks": [
            {
                "name": c.name,
                "ok": c.ok,
                "severity": c.severity,
                "reason": c.reason,
                "remediation": c.remediation,
                "details": c.details,
                "duration_s": c.duration_s,
            }
            for c in report.checks
        ],
    }

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    print(json.dumps(data, sort_keys=True))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
