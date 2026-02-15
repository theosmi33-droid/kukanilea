from __future__ import annotations

import argparse
import json

from app.autonomy.source_scan import ConfigError, scan_sources_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--budget-ms", type=int, default=1500)
    args = parser.parse_args()

    try:
        result = scan_sources_once(args.tenant, budget_ms=args.budget_ms)
    except ConfigError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "config_error",
                    "reason": str(exc),
                },
                sort_keys=True,
            )
        )
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "unexpected_error",
                    "reason": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 3

    print(json.dumps(result, sort_keys=True))
    return 0 if bool(result.get("ok", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
