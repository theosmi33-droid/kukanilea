from __future__ import annotations

from app.bench.hardening_latency import evaluate_thresholds, run_latency_suite


def test_run_latency_suite_mock_mode_collects_percentiles() -> None:
    report = run_latency_suite(requests_count=2, use_real_ai=False)

    assert report["mode"] == "mock_ai"
    assert int(report["requests"]) == 2
    assert int((report["ai_chat"] or {}).get("errors") or 0) == 0
    assert int((report["search"] or {}).get("errors") or 0) == 0
    assert float((report["ai_chat"] or {}).get("p95_ms") or 0.0) >= float(
        (report["ai_chat"] or {}).get("p50_ms") or 0.0
    )
    assert float((report["search"] or {}).get("p95_ms") or 0.0) >= float(
        (report["search"] or {}).get("p50_ms") or 0.0
    )


def test_evaluate_thresholds_warn_vs_fail_profiles() -> None:
    report = {
        "ai_chat": {"p95_ms": 150.0},
        "search": {"p95_ms": 120.0},
    }
    thresholds = {
        "dev": {
            "ai_p95_ms": {"max": 100.0, "severity": "warn"},
            "search_p95_ms": {"max": 110.0, "severity": "warn"},
        },
        "ci": {
            "ai_p95_ms": {"max": 100.0, "severity": "fail"},
            "search_p95_ms": {"max": 110.0, "severity": "fail"},
        },
    }

    dev_gate = evaluate_thresholds(report, thresholds=thresholds, profile="dev")
    assert int(dev_gate["warn_count"]) == 2
    assert int(dev_gate["fail_count"]) == 0

    ci_gate = evaluate_thresholds(report, thresholds=thresholds, profile="ci")
    assert int(ci_gate["warn_count"]) == 0
    assert int(ci_gate["fail_count"]) == 2
