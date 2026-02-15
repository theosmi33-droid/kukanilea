from __future__ import annotations

import argparse
import json

from app.autonomy.maintenance import run_backup_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--tenant")
    parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args()

    if not args.backup:
        print(json.dumps({"ok": False, "error": "no_action"}, sort_keys=True))
        return 2

    try:
        result = run_backup_once(
            tenant_id=args.tenant,
            rotate=bool(args.rotate),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "backup_failed",
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
