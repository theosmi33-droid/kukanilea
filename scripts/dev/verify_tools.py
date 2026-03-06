#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.tool_loader import load_all_tools


def main() -> int:
    report = load_all_tools()

    print("Core Tool Interface Verification")
    print("=" * 34)
    print(f"ok: {report['ok']}")
    print(f"imported modules: {len(report['imported_modules'])}")
    print(f"loaded tools: {len(report['loaded_tools'])}")
    print(f"failed modules: {len(report['failed_modules'])}")
    print(f"failed tools: {len(report['failed_tools'])}")

    if report["failed_modules"]:
        print("\nFailed modules:")
        for item in report["failed_modules"]:
            print(f"- {item['module']}: {item['error']}")

    if report["failed_tools"]:
        print("\nFailed tools:")
        for item in report["failed_tools"]:
            errors = item.get("errors") or [item.get("error", "unknown error")]
            print(f"- {item['tool']}: {', '.join(errors)}")

    print("\nJSON report:")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
