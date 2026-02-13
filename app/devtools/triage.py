from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _run_step(label: str, command: list[str]) -> None:
    print(f"[triage] {label}: {' '.join(command)}")
    completed = subprocess.run(command)
    if completed.returncode != 0:
        raise RuntimeError(f"step_failed:{label}")


def _run_optional_ruff() -> None:
    if shutil.which("ruff") is None:
        print("[triage] ruff not installed, skipping")
        return
    _run_step("ruff_check", ["ruff", "check", ".", "--fix"])
    _run_step("ruff_format", ["ruff", "format", "."])


def _baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "bench" / "baseline.json"


def _run_benchmarks(
    *, write_baseline: bool, max_regression_pct: float
) -> tuple[dict[str, float], bool]:
    from app.bench import benchmarks as bench_mod

    current = bench_mod.run_all()
    print(json.dumps({"benchmarks": current}, sort_keys=True))

    baseline_file = _baseline_path()
    if write_baseline:
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_file.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"[triage] wrote baseline: {baseline_file}")
        return current, True

    if not baseline_file.exists():
        print(f"[triage] baseline missing at {baseline_file}, skipping regression gate")
        return current, True

    try:
        baseline = json.loads(baseline_file.read_text())
    except Exception as exc:
        print(f"[triage] failed to read baseline: {exc}")
        return current, False

    ok = True
    for name, current_value in current.items():
        base_value = baseline.get(name)
        if base_value is None:
            print(f"[triage] baseline missing metric {name}, skipping")
            continue
        base = float(base_value)
        cur = float(current_value)
        if base <= 0.0:
            if cur > 0.0:
                print(
                    f"[triage] regression {name}: current={cur:.6f}s base={base:.6f}s"
                )
                ok = False
            continue
        threshold = base * (1.0 + (max_regression_pct / 100.0))
        if cur > threshold:
            print(
                "[triage] regression "
                f"{name}: current={cur:.6f}s base={base:.6f}s "
                f"threshold={threshold:.6f}s"
            )
            ok = False
    return current, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run quality triage checks")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fast", action="store_true", help="Run targeted fast tests")
    mode.add_argument("--full", action="store_true", help="Run full test suite")
    parser.add_argument("--bench", action="store_true", help="Run benchmark checks")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write benchmark baseline and skip regression failure",
    )
    parser.add_argument(
        "--max-regression-pct",
        type=float,
        default=30.0,
        help="Maximum allowed benchmark regression in percent",
    )
    args = parser.parse_args(argv)

    try:
        _run_step("compileall", [sys.executable, "-m", "compileall", "-q", "."])
        _run_step("smoke", [sys.executable, "-m", "app.smoke"])

        if args.full:
            pytest_cmd = ["pytest", "-q"]
        else:
            pytest_cmd = [
                "pytest",
                "-q",
                "tests/test_eventlog.py",
                "tests/test_time_tracking.py",
                "tests/test_benchmarks.py",
            ]
        _run_step("pytest", pytest_cmd)

        _run_optional_ruff()

        if args.bench:
            _, bench_ok = _run_benchmarks(
                write_baseline=args.write_baseline,
                max_regression_pct=args.max_regression_pct,
            )
            if not bench_ok:
                print("[triage] benchmark regression detected")
                return 1

        print("[triage] all checks passed")
        return 0
    except RuntimeError as exc:
        print(f"[triage] failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
