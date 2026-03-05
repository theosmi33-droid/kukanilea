from __future__ import annotations

import json

from scripts.perf import benchmark_gate as perf_gate


def test_aggregate_reports_expected_statistics() -> None:
    aggregated = perf_gate._aggregate([10.0, 20.0, 30.0, 40.0, 50.0])

    assert aggregated["p50_ms"] == 30.0
    assert aggregated["p95_ms"] == 50.0
    assert aggregated["max_ms"] == 50.0
    assert aggregated["avg_ms"] == 30.0


def test_evaluate_metric_pass_when_below_warn_threshold() -> None:
    result = perf_gate.evaluate_metric("dashboard_ttfb_ms", 120.0)

    assert result["status"] == "pass"
    assert result["threshold"]["warn_ms"] == 250.0


def test_evaluate_metric_warn_when_p95_hits_warn_threshold() -> None:
    result = perf_gate.evaluate_metric("dashboard_ttfb_ms", 260.0)

    assert result["status"] == "warn"


def test_dashboard_regression_sets_fail_status() -> None:
    """Regression guard: dashboard latency spikes must hard-fail the gate."""
    result = perf_gate.evaluate_metric("dashboard_ttfb_ms", 650.0)

    assert result["status"] == "fail"


def test_api_summary_regression_sets_fail_status() -> None:
    """Regression guard: API summary degradation should fail CI gate."""
    result = perf_gate.evaluate_metric("api_summary_latency_ms", 500.0)

    assert result["status"] == "fail"


def test_write_outputs_creates_markdown_and_json(tmp_path) -> None:
    report = {
        "timestamp": "2026-03-05T10:00:00+00:00",
        "samples": 2,
        "metrics": {
            "app_start_time_ms": {"p50_ms": 100.0, "p95_ms": 120.0, "max_ms": 120.0, "avg_ms": 110.0},
            "dashboard_ttfb_ms": {"p50_ms": 80.0, "p95_ms": 90.0, "max_ms": 90.0, "avg_ms": 85.0},
            "api_summary_latency_ms": {
                "p50_ms": 70.0,
                "p95_ms": 88.0,
                "max_ms": 90.0,
                "avg_ms": 76.0,
                "by_tool": {
                    "aufgaben": {"p95_ms": 80.0, "avg_ms": 60.0, "max_ms": 81.0},
                    "projekte": {"p95_ms": 90.0, "avg_ms": 75.0, "max_ms": 94.0},
                    "kalender": {"p95_ms": 86.0, "avg_ms": 69.0, "max_ms": 88.0},
                },
            },
        },
        "gate": {
            "app_start_time_ms": {"status": "pass", "threshold": {"warn_ms": 1500.0, "fail_ms": 2500.0}, "p95_ms": 120.0},
            "dashboard_ttfb_ms": {"status": "pass", "threshold": {"warn_ms": 250.0, "fail_ms": 450.0}, "p95_ms": 90.0},
            "api_summary_latency_ms": {"status": "pass", "threshold": {"warn_ms": 180.0, "fail_ms": 320.0}, "p95_ms": 88.0},
            "overall_status": "pass",
        },
    }

    json_path = tmp_path / "perf.json"
    md_path = tmp_path / "KPIS.md"
    perf_gate.write_outputs(report, json_path=json_path, markdown_path=md_path)

    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert persisted["gate"]["overall_status"] == "pass"
    assert "| dashboard_ttfb_ms |" in markdown
    assert "| projekte |" in markdown
