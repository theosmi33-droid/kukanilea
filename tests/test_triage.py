from __future__ import annotations

import json
from pathlib import Path

from app.devtools import triage


def _ok_result() -> dict[str, object]:
    return {
        "ok": True,
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "secs": 0.01,
        "timeout": False,
    }


def test_ci_fails_without_ruff(tmp_path: Path, monkeypatch) -> None:
    report_path = tmp_path / "triage.json"

    monkeypatch.setattr(triage.shutil, "which", lambda name: None)
    monkeypatch.setattr(triage, "_run_bench_step", lambda args, steps: True)
    monkeypatch.setattr(triage, "run_cmd", lambda args, timeout=None: _ok_result())

    rc = triage.main(["--ci", "--json-out", str(report_path)])
    assert rc != 0
    report = json.loads(report_path.read_text())
    ruff_step = next(step for step in report["steps"] if step["name"] == "ruff")
    assert ruff_step["ok"] is False
    assert "strict/ci" in ruff_step["reason"]


def test_require_baseline_fails_when_missing(tmp_path: Path, monkeypatch) -> None:
    report_path = tmp_path / "triage.json"
    baseline_path = tmp_path / "missing_baseline.json"

    monkeypatch.setattr(triage, "_baseline_path", lambda: baseline_path)
    monkeypatch.setattr(triage.shutil, "which", lambda name: "/usr/bin/ruff")

    def fake_run_cmd(args: list[str], timeout: float | None = None):
        del timeout
        return _ok_result()

    monkeypatch.setattr(triage, "run_cmd", fake_run_cmd)

    import app.bench.benchmarks as bm

    monkeypatch.setattr(
        bm,
        "run_benchmark_suite",
        lambda runs=5, warmup=1, time_budget_secs=20.0: {
            "event_verify_chain_synth_2000": 0.5,
            "recompute_task_duration_synth": 0.6,
        },
    )

    rc = triage.main(["--bench", "--require-baseline", "--json-out", str(report_path)])
    assert rc != 0
    report = json.loads(report_path.read_text())
    bench = next(step for step in report["steps"] if step["name"] == "bench")
    assert bench["ok"] is False
    assert bench["reason"] == "baseline missing"


def test_json_report_written_on_failure(tmp_path: Path, monkeypatch) -> None:
    report_path = tmp_path / "triage.json"

    def fake_run_cmd(args: list[str], timeout: float | None = None):
        del timeout
        if args[:4] == [triage.sys.executable, "-m", "compileall", "-q"]:
            return {
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": "compile error",
                "secs": 0.02,
                "timeout": False,
            }
        return _ok_result()

    monkeypatch.setattr(triage, "run_cmd", fake_run_cmd)
    rc = triage.main(["--fast", "--json-out", str(report_path)])

    assert rc != 0
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert report["overall_ok"] is False
    compile_step = next(step for step in report["steps"] if step["name"] == "compileall")
    assert compile_step["ok"] is False
