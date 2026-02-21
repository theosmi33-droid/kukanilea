#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bench.hardening_latency import (  # noqa: E402
    evaluate_thresholds,
    load_thresholds,
    run_latency_suite,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run hardening latency benchmark for AI chat and search."
    )
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--real-ai", action="store_true")
    parser.add_argument("--profile", choices=["dev", "ci"], default="dev")
    parser.add_argument("--threshold-file", type=str, default="")
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()

    report = run_latency_suite(requests_count=args.requests, use_real_ai=args.real_ai)
    thresholds = load_thresholds(args.threshold_file or None)
    gate = evaluate_thresholds(report, thresholds=thresholds, profile=args.profile)
    payload = {"report": report, "gate": gate}

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 1 if int(gate.get("fail_count") or 0) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
