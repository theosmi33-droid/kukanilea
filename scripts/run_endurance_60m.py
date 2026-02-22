#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bench.hardening_latency import run_latency_suite  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _run_pytest_e2e(timeout_seconds: int) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/e2e/test_hardening_smoke.py::test_hardening_top_flows_smoke",
        "tests/e2e/test_hardening_smoke.py::test_hardening_error_shell_navigation",
    ]
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=max(30, int(timeout_seconds)),
        cwd=str(ROOT),
    )
    duration_ms = round((time.perf_counter() - start) * 1000.0, 3)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    lowered = output.lower()
    if proc.returncode == 0:
        status = "pass"
    elif "skipped" in lowered and "failed" not in lowered:
        status = "skipped"
    else:
        status = "fail"
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "duration_ms": duration_ms,
        "status": status,
        "output": output,
    }


def _ensure_dirs(base: Path) -> tuple[Path, Path]:
    failures = base / "e2e_failures"
    base.mkdir(parents=True, exist_ok=True)
    failures.mkdir(parents=True, exist_ok=True)
    return base, failures


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run endurance benchmark with repeated E2E smoke and latency snapshots."
    )
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--sanity", action="store_true")
    parser.add_argument("--e2e-interval-seconds", type=int, default=180)
    parser.add_argument("--latency-interval-seconds", type=int, default=300)
    parser.add_argument("--latency-requests", type=int, default=10)
    parser.add_argument("--real-ai", action="store_true")
    parser.add_argument("--output-dir", type=str, default="output/endurance")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    duration_minutes = 5 if args.sanity else max(1, int(args.duration_minutes))
    output_dir, failure_dir = _ensure_dirs((ROOT / args.output_dir).resolve())
    summary_path = output_dir / "summary.json"
    latency_csv_path = output_dir / "latency.csv"

    playwright_installed = importlib.util.find_spec("playwright") is not None
    start_ts = time.time()
    end_ts = start_ts + (duration_minutes * 60)
    next_e2e = start_ts
    next_latency = start_ts

    e2e_runs: list[dict[str, Any]] = []
    latency_runs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    while time.time() < end_ts:
        now = time.time()
        if now >= next_e2e:
            run_id = len(e2e_runs) + 1
            if playwright_installed:
                result = _run_pytest_e2e(
                    timeout_seconds=args.e2e_interval_seconds + 120
                )
            else:
                result = {
                    "command": [],
                    "returncode": 0,
                    "duration_ms": 0.0,
                    "status": "skipped",
                    "output": "playwright not installed; e2e run skipped",
                }
            result["run_id"] = run_id
            result["ts"] = _utc_now_iso()
            e2e_runs.append(result)

            log_path = failure_dir / f"e2e_iter_{run_id:03d}.log"
            log_path.write_text(result["output"], encoding="utf-8")
            result["log_path"] = str(log_path)

            if result["status"] == "fail":
                failures.append(
                    {
                        "type": "e2e",
                        "run_id": run_id,
                        "timestamp": result["ts"],
                        "log_path": str(log_path),
                    }
                )

            next_e2e = now + max(30, int(args.e2e_interval_seconds))

        now = time.time()
        if now >= next_latency:
            run_id = len(latency_runs) + 1
            report = run_latency_suite(
                requests_count=max(1, int(args.latency_requests)),
                use_real_ai=bool(args.real_ai),
            )
            sample = {
                "run_id": run_id,
                "ts": _utc_now_iso(),
                "mode": report.get("mode"),
                "ai_p50_ms": (report.get("ai_chat") or {}).get("p50_ms"),
                "ai_p95_ms": (report.get("ai_chat") or {}).get("p95_ms"),
                "ai_errors": (report.get("ai_chat") or {}).get("errors"),
                "search_p50_ms": (report.get("search") or {}).get("p50_ms"),
                "search_p95_ms": (report.get("search") or {}).get("p95_ms"),
                "search_errors": (report.get("search") or {}).get("errors"),
            }
            latency_runs.append(sample)
            if (
                int(sample["ai_errors"] or 0) > 0
                or int(sample["search_errors"] or 0) > 0
            ):
                failures.append(
                    {
                        "type": "latency",
                        "run_id": run_id,
                        "timestamp": sample["ts"],
                        "reason": "non_zero_error_count",
                    }
                )
            next_latency = now + max(30, int(args.latency_interval_seconds))

        time.sleep(1.0)

    with latency_csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "run_id",
                "ts",
                "mode",
                "ai_p50_ms",
                "ai_p95_ms",
                "ai_errors",
                "search_p50_ms",
                "search_p95_ms",
                "search_errors",
            ],
        )
        writer.writeheader()
        for row in latency_runs:
            writer.writerow(row)

    total_seconds = round(time.time() - start_ts, 2)
    summary = {
        "started_at": datetime.fromtimestamp(start_ts, UTC).isoformat(),
        "ended_at": _utc_now_iso(),
        "duration_seconds": total_seconds,
        "duration_minutes_configured": duration_minutes,
        "playwright_installed": playwright_installed,
        "e2e_total_runs": len(e2e_runs),
        "e2e_pass_runs": sum(1 for item in e2e_runs if item["status"] == "pass"),
        "e2e_skipped_runs": sum(1 for item in e2e_runs if item["status"] == "skipped"),
        "e2e_fail_runs": sum(1 for item in e2e_runs if item["status"] == "fail"),
        "latency_total_runs": len(latency_runs),
        "latency_ai_error_runs": sum(
            1 for item in latency_runs if int(item.get("ai_errors") or 0) > 0
        ),
        "latency_search_error_runs": sum(
            1 for item in latency_runs if int(item.get("search_errors") or 0) > 0
        ),
        "failures": failures,
        "artifacts": {
            "summary_json": str(summary_path),
            "latency_csv": str(latency_csv_path),
            "e2e_failure_logs_dir": str(failure_dir),
        },
        "e2e_runs": e2e_runs,
        "latency_runs": latency_runs,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rc = 1 if failures else 0
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
