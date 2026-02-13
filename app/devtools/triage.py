from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_cmd(args: list[str], timeout: float | None = None) -> dict[str, Any]:
    """Run subprocess command without shell and capture outputs."""
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": int(completed.returncode),
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "secs": time.perf_counter() - started,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            "secs": time.perf_counter() - started,
            "timeout": True,
        }


def _baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "bench" / "baseline.json"


def _git_commit() -> str | None:
    result = run_cmd(["git", "rev-parse", "--short", "HEAD"], timeout=5.0)
    if result["ok"]:
        return str(result["stdout"]).strip()
    return None


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run quality triage checks")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fast", action="store_true", help="Run targeted fast tests")
    mode.add_argument("--full", action="store_true", help="Run full test suite")
    parser.add_argument("--bench", action="store_true", help="Run benchmark checks")
    parser.add_argument(
        "--write-baseline", action="store_true", help="Write benchmark baseline"
    )
    parser.add_argument("--max-regression-pct", type=float, default=30.0)

    parser.add_argument(
        "--strict", action="store_true", help="Fail on missing optional tools"
    )
    parser.add_argument(
        "--require-baseline",
        action="store_true",
        help="Require benchmark baseline when --bench",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Enable CI mode (= --strict --full --bench --require-baseline)",
    )
    parser.add_argument("--json-out", default="triage_report.json")
    parser.add_argument("--bench-factor", type=float, default=1.30)
    parser.add_argument("--bench-runs", type=int, default=5)
    parser.add_argument("--bench-warmup", type=int, default=1)
    parser.add_argument("--bench-time-budget", type=float, default=20.0)
    return parser.parse_args(argv)


def _normalize_modes(args: argparse.Namespace, argv: list[str] | None) -> None:
    if args.ci:
        args.strict = True
        args.full = True
        args.fast = False
        args.bench = True
        args.require_baseline = True

    arglist = argv or []
    if "--bench-factor" not in arglist and args.max_regression_pct != 30.0:
        args.bench_factor = 1.0 + (float(args.max_regression_pct) / 100.0)


def _record_step(
    steps: list[dict[str, Any]],
    *,
    name: str,
    result: dict[str, Any] | None = None,
    ok: bool | None = None,
    skipped: bool = False,
    reason: str = "",
    extra: dict[str, Any] | None = None,
) -> bool:
    if result is None:
        result = {"ok": bool(ok), "secs": 0.0, "stdout": "", "stderr": ""}
    entry = {
        "name": name,
        "ok": bool(result.get("ok") if ok is None else ok),
        "secs": float(result.get("secs", 0.0) or 0.0),
        "skipped": bool(skipped),
        "stdout": str(result.get("stdout", "") or ""),
        "stderr": str(result.get("stderr", "") or ""),
        "reason": reason,
    }
    if extra:
        entry.update(extra)
    steps.append(entry)
    return bool(entry["ok"])


def _load_baseline_metrics(raw: Any) -> dict[str, float]:
    if isinstance(raw, dict):
        if isinstance(raw.get("metrics"), dict):
            return {k: float(v) for k, v in raw["metrics"].items()}
        return {k: float(v) for k, v in raw.items() if isinstance(v, (int, float))}
    return {}


def _run_bench_step(args: argparse.Namespace, steps: list[dict[str, Any]]) -> bool:
    if not args.bench:
        return _record_step(
            steps,
            name="bench",
            ok=True,
            skipped=True,
            reason="bench disabled",
        )

    from app.bench.benchmarks import run_benchmark_suite

    started = time.perf_counter()
    metrics: dict[str, float] = {}
    try:
        metrics = run_benchmark_suite(
            runs=args.bench_runs,
            warmup=args.bench_warmup,
            time_budget_secs=args.bench_time_budget,
        )
    except Exception as exc:
        return _record_step(
            steps,
            name="bench",
            ok=False,
            reason=f"benchmark_failed: {exc}",
            extra={"metrics": metrics},
            result={
                "ok": False,
                "secs": time.perf_counter() - started,
                "stdout": "",
                "stderr": str(exc),
            },
        )

    baseline_file = _baseline_path()
    step_extra: dict[str, Any] = {
        "metrics": metrics,
        "baseline_path": str(baseline_file),
        "bench_factor": float(args.bench_factor),
        "runs": int(args.bench_runs),
        "warmup": int(args.bench_warmup),
        "time_budget_secs": float(args.bench_time_budget),
    }

    if args.write_baseline:
        baseline_file.parent.mkdir(parents=True, exist_ok=True)
        baseline_payload = {
            "meta": {
                "created_at_utc": _utcnow_iso(),
                "python_version": sys.version,
                "platform": platform.platform(),
                "git_commit": _git_commit(),
            },
            "metrics": metrics,
        }
        baseline_file.write_text(
            json.dumps(baseline_payload, indent=2, sort_keys=True) + "\n"
        )
        step_extra["baseline_written"] = True
        return _record_step(
            steps,
            name="bench",
            ok=True,
            result={
                "ok": True,
                "secs": time.perf_counter() - started,
                "stdout": "",
                "stderr": "",
            },
            extra=step_extra,
        )

    if not baseline_file.exists():
        required = bool(args.require_baseline or args.strict or args.ci)
        return _record_step(
            steps,
            name="bench",
            ok=not required,
            reason="baseline missing",
            result={
                "ok": not required,
                "secs": time.perf_counter() - started,
                "stdout": "",
                "stderr": "",
            },
            extra={**step_extra, "skipped_compare": True},
        )

    try:
        baseline_raw = json.loads(baseline_file.read_text())
        baseline_metrics = _load_baseline_metrics(baseline_raw)
    except Exception as exc:
        return _record_step(
            steps,
            name="bench",
            ok=False,
            reason=f"baseline_parse_failed: {exc}",
            result={
                "ok": False,
                "secs": time.perf_counter() - started,
                "stdout": "",
                "stderr": str(exc),
            },
            extra=step_extra,
        )

    regressions: list[dict[str, Any]] = []
    factor = float(args.bench_factor)
    for metric, current in metrics.items():
        base = baseline_metrics.get(metric)
        if base is None:
            continue
        threshold = float(base) * factor
        if float(current) > threshold:
            regressions.append(
                {
                    "metric": metric,
                    "current": float(current),
                    "baseline": float(base),
                    "threshold": float(threshold),
                }
            )

    ok = len(regressions) == 0
    return _record_step(
        steps,
        name="bench",
        ok=ok,
        reason="" if ok else "benchmark regression detected",
        result={
            "ok": ok,
            "secs": time.perf_counter() - started,
            "stdout": "",
            "stderr": "",
        },
        extra={**step_extra, "regressions": regressions},
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _normalize_modes(args, argv)

    report: dict[str, Any] = {
        "created_at_utc": _utcnow_iso(),
        "argv": argv if argv is not None else sys.argv[1:],
        "cwd": os.getcwd(),
        "strict": bool(args.strict),
        "ci": bool(args.ci),
        "steps": [],
        "overall_ok": False,
    }
    report_path = Path(args.json_out)

    exit_code = 0
    try:
        steps: list[dict[str, Any]] = report["steps"]

        if args.write_baseline and not args.bench:
            _record_step(
                steps,
                name="bench",
                ok=False,
                reason="--write-baseline requires --bench",
                result={"ok": False, "secs": 0.0, "stdout": "", "stderr": ""},
            )
            exit_code = 2
            return exit_code

        compile_result = run_cmd([sys.executable, "-m", "compileall", "-q", "."])
        if not _record_step(steps, name="compileall", result=compile_result):
            exit_code = 2
            return exit_code

        smoke_result = run_cmd([sys.executable, "-m", "app.smoke"])
        if not _record_step(steps, name="smoke", result=smoke_result):
            exit_code = 2
            return exit_code

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
        pytest_result = run_cmd(pytest_cmd)
        if not _record_step(steps, name="pytest", result=pytest_result):
            exit_code = 2
            return exit_code

        ruff_path = shutil.which("ruff")
        if ruff_path is None:
            strict_ruff = bool(args.strict or args.ci)
            if not _record_step(
                steps,
                name="ruff",
                ok=not strict_ruff,
                skipped=not strict_ruff,
                reason="ruff required in strict/ci"
                if strict_ruff
                else "ruff not installed",
            ):
                exit_code = 2
                return exit_code
        else:
            started = time.perf_counter()
            check = run_cmd([ruff_path, "check", ".", "--fix"])
            fmt = run_cmd([ruff_path, "format", "."])
            ok = bool(check["ok"] and fmt["ok"])
            if not _record_step(
                steps,
                name="ruff",
                ok=ok,
                result={
                    "ok": ok,
                    "secs": time.perf_counter() - started,
                    "stdout": (check.get("stdout", "") or "")
                    + (fmt.get("stdout", "") or ""),
                    "stderr": (check.get("stderr", "") or "")
                    + (fmt.get("stderr", "") or ""),
                },
                extra={"check": check, "format": fmt},
            ):
                exit_code = 2
                return exit_code

        if not _run_bench_step(args, steps):
            exit_code = 2
            return exit_code

        exit_code = 0
        return exit_code
    finally:
        report["overall_ok"] = exit_code == 0 and all(
            bool(step.get("ok")) for step in report.get("steps", [])
        )
        report["exit_code"] = exit_code
        _write_report(report_path, report)
        print(json.dumps({"json_report": str(report_path), "exit_code": exit_code}))


if __name__ == "__main__":
    raise SystemExit(main())
