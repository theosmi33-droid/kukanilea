from __future__ import annotations

import argparse
import contextlib
import json
import os
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class Threshold:
    warn_ms: float
    fail_ms: float


THRESHOLDS: dict[str, Threshold] = {
    "app_start_time_ms": Threshold(warn_ms=1500.0, fail_ms=2500.0),
    "dashboard_ttfb_ms": Threshold(warn_ms=250.0, fail_ms=450.0),
    "api_summary_latency_ms": Threshold(warn_ms=180.0, fail_ms=320.0),
}

SUMMARY_TOOLS = ("aufgaben", "projekte", "kalender")


def _aggregate(values_ms: list[float]) -> dict[str, float]:
    if not values_ms:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0, "avg_ms": 0.0}

    p50 = statistics.median(values_ms)
    sorted_vals = sorted(values_ms)
    p95_index = min(len(sorted_vals) - 1, max(0, round((len(sorted_vals) - 1) * 0.95)))
    return {
        "p50_ms": round(p50, 2),
        "p95_ms": round(sorted_vals[p95_index], 2),
        "max_ms": round(max(values_ms), 2),
        "avg_ms": round(statistics.mean(values_ms), 2),
    }


def evaluate_metric(metric_name: str, p95_ms: float) -> dict[str, Any]:
    threshold = THRESHOLDS[metric_name]
    status = "pass"
    if p95_ms >= threshold.fail_ms:
        status = "fail"
    elif p95_ms >= threshold.warn_ms:
        status = "warn"

    return {
        "status": status,
        "threshold": asdict(threshold),
        "p95_ms": round(p95_ms, 2),
    }


def _seed_perf_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "perf-bot"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def _seed_perf_user(app) -> None:
    from app.auth import hash_password

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now_iso = datetime.now(timezone.utc).isoformat()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now_iso)
        auth_db.upsert_user("perf-bot", hash_password("perf-bot"), now_iso)
        auth_db.upsert_membership("perf-bot", "KUKANILEA", "DEV", now_iso)


@contextlib.contextmanager
def _isolated_perf_datastores() -> Any:
    tracked_keys = (
        "KUKANILEA_USER_DATA_ROOT",
        "KUKANILEA_AUTH_DB",
        "KUKANILEA_CORE_DB",
        "KUKANILEA_LICENSE_PATH",
        "KUKANILEA_TRIAL_PATH",
        "KUKANILEA_RESEARCH_CACHE_PATH",
    )
    previous = {key: os.environ.get(key) for key in tracked_keys}

    with tempfile.TemporaryDirectory(prefix="kukanilea-perf-") as temp_root:
        root = Path(temp_root)
        os.environ["KUKANILEA_USER_DATA_ROOT"] = str(root)
        os.environ["KUKANILEA_AUTH_DB"] = str(root / "auth.sqlite3")
        os.environ["KUKANILEA_CORE_DB"] = str(root / "core.sqlite3")
        os.environ["KUKANILEA_LICENSE_PATH"] = str(root / "license.json")
        os.environ["KUKANILEA_TRIAL_PATH"] = str(root / "trial.json")
        os.environ["KUKANILEA_RESEARCH_CACHE_PATH"] = str(root / "research_cache.json")

        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def run_benchmarks(samples: int = 3) -> dict[str, Any]:
    os.environ.setdefault("KUKANILEA_DISABLE_DAEMONS", "1")

    startup_values: list[float] = []
    dashboard_values: list[float] = []
    summary_values: list[float] = []
    summary_by_tool: dict[str, list[float]] = {tool: [] for tool in SUMMARY_TOOLS}

    with _isolated_perf_datastores():
        from app import create_app

        for _ in range(samples):
            start = time.perf_counter()
            app = create_app()
            startup_values.append((time.perf_counter() - start) * 1000)

            _seed_perf_user(app)
            client = app.test_client()
            _seed_perf_session(client)

            dashboard_start = time.perf_counter()
            dashboard_response = client.get("/dashboard")
            dashboard_values.append((time.perf_counter() - dashboard_start) * 1000)
            if dashboard_response.status_code != 200:
                raise RuntimeError(f"/dashboard returned HTTP {dashboard_response.status_code}")

            for tool in SUMMARY_TOOLS:
                summary_start = time.perf_counter()
                response = client.get(f"/api/{tool}/summary")
                duration_ms = (time.perf_counter() - summary_start) * 1000
                summary_values.append(duration_ms)
                summary_by_tool[tool].append(duration_ms)
                if response.status_code != 200:
                    raise RuntimeError(f"/api/{tool}/summary returned HTTP {response.status_code}")

    metrics = {
        "app_start_time_ms": _aggregate(startup_values),
        "dashboard_ttfb_ms": _aggregate(dashboard_values),
        "api_summary_latency_ms": {
            **_aggregate(summary_values),
            "by_tool": {tool: _aggregate(values) for tool, values in summary_by_tool.items()},
        },
    }

    gate = {
        name: evaluate_metric(name, metric["p95_ms"])
        for name, metric in metrics.items()
        if name in THRESHOLDS
    }
    gate["overall_status"] = "fail" if any(item["status"] == "fail" for item in gate.values()) else (
        "warn" if any(item["status"] == "warn" for item in gate.values()) else "pass"
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "samples": samples,
        "metrics": metrics,
        "gate": gate,
    }


def write_outputs(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    gate = report["gate"]
    metrics = report["metrics"]
    lines = [
        "# KPI Status",
        "",
        f"_Generated: {report['timestamp']}_",
        "",
        "## Performance KPI Gate",
        "",
        f"* Overall status: **{gate['overall_status']}**",
        f"* Samples: **{report['samples']}**",
        "",
        "| KPI | P95 (ms) | Warn (ms) | Fail (ms) | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]

    for metric_name in ("app_start_time_ms", "dashboard_ttfb_ms", "api_summary_latency_ms"):
        metric = metrics[metric_name]
        result = gate[metric_name]
        lines.append(
            f"| {metric_name} | {metric['p95_ms']} | {result['threshold']['warn_ms']} | {result['threshold']['fail_ms']} | {result['status']} |"
        )

    lines.extend(
        [
            "",
            "## API Summary Details",
            "",
            "| Tool | P95 (ms) | Avg (ms) | Max (ms) |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for tool, values in metrics["api_summary_latency_ms"]["by_tool"].items():
        lines.append(f"| {tool} | {values['p95_ms']} | {values['avg_ms']} | {values['max_ms']} |")

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Performance KPI benchmark gate")
    parser.add_argument("--samples", type=int, default=3, help="Number of benchmark rounds")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("docs/status/perf_kpi_latest.json"),
        help="Path for JSON benchmark artifact",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=Path("docs/status/KPIS.md"),
        help="Path for markdown KPI status",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_benchmarks(samples=args.samples)
    write_outputs(report, json_path=args.json_out, markdown_path=args.md_out)

    overall = report["gate"]["overall_status"]
    print(json.dumps(report["gate"], indent=2))
    if overall == "fail":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
