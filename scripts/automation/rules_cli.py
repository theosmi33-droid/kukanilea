#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.automation import load_rules_from_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Load automation rules from YAML/JSON files")
    parser.add_argument("--tenant", default="KUKANILEA")
    parser.add_argument("--rules-dir", default="app/modules/automation/examples")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()

    ids = load_rules_from_dir(
        tenant_id=args.tenant,
        rules_dir=Path(args.rules_dir),
        db_path=args.db_path,
    )
    print(json.dumps({"ok": True, "created": len(ids), "rule_ids": ids}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
