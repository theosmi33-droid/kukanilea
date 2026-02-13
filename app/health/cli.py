#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.health import checks
from app.health.core import HealthRunner


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in sorted(value.items(), key=lambda kv: kv[0])}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str):
        s = value.replace(str(Path.home()), "<home>")
        for marker in ["/tmp/", "/var/folders/", "\\Temp\\", "\\tmp\\"]:
            if marker in s:
                idx = s.find(marker)
                return s[:idx] + "<tmp>"
        return s
    if isinstance(value, float):
        return round(value, 3)
    return value


def report_to_jsonable(report) -> dict[str, Any]:
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
                "duration_s": round(float(c.duration_s), 3),
            }
            for c in sorted(report.checks, key=lambda item: item.name)
        ],
    }
    return _sanitize(data)


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

    data = report_to_jsonable(report)

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    print(json.dumps(data, sort_keys=True))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
