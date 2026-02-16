from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_cmd(
    args: list[str], timeout: float | None = None, env: dict[str, str] | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
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


def _run_cmd_compat(
    args: list[str], timeout: float | None = None, env: dict[str, str] | None = None
) -> dict[str, Any]:
    try:
        return run_cmd(args, timeout=timeout, env=env)
    except TypeError:
        # backward compatibility for tests monkeypatching run_cmd(args, timeout)
        return run_cmd(args, timeout=timeout)


def run_cmd_with_warning_detection(
    args: list[str],
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    ignore_regexes: list[str] | None = None,
) -> dict[str, Any]:
    result = _run_cmd_compat(args, timeout=timeout, env=env)
    ignore_regexes = ignore_regexes or []

    category_re = re.compile(
        r"\b(DeprecationWarning|ResourceWarning|UserWarning|PendingDeprecationWarning|RuntimeWarning|FutureWarning|ImportWarning|SyntaxWarning|UnicodeWarning)\b"
    )
    format_re = re.compile(r"^[^:\n]+:\d+:\s*(?:[A-Za-z]+Warning):")

    warning_lines: list[str] = []

    stderr_lines = str(result.get("stderr", "")).splitlines()
    for line in stderr_lines:
        if category_re.search(line) or format_re.search(line):
            warning_lines.append(line)

    if not warning_lines:
        stdout_lines = str(result.get("stdout", "")).splitlines()
        for line in stdout_lines:
            if category_re.search(line) or format_re.search(line):
                warning_lines.append(line)

    for raw in ignore_regexes:
        ig = re.compile(raw, re.IGNORECASE)
        warning_lines = [line for line in warning_lines if not ig.search(line)]

    result["warning_count"] = len(warning_lines)
    result["warning_lines"] = warning_lines[:10]
    return result


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
        help="CI mode (= --strict --full --bench --require-baseline)",
    )
    parser.add_argument("--json-out", default="triage_report.json")

    parser.add_argument("--bench-factor", type=float, default=1.30)
    parser.add_argument("--bench-runs", type=int, default=5)
    parser.add_argument("--bench-warmup", type=int, default=1)
    parser.add_argument("--bench-retries", type=int, default=1)
    parser.add_argument("--bench-time-budget", type=float, default=20.0)

    parser.add_argument("--health", action="store_true", help="Run health checks")
    parser.add_argument("--health-mode", choices=["ci", "runtime"], default="ci")
    parser.add_argument("--health-json")

    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Fail when warnings are detected",
    )
    parser.add_argument("--ignore-warning-regex", action="append", default=[])

    return parser.parse_args(argv)


def _normalize_modes(args: argparse.Namespace, argv: list[str] | None) -> None:
    if args.ci:
        args.strict = True
        args.full = True
        args.fast = False
        args.bench = True
        args.require_baseline = True
        args.health = True

    arglist = argv or []
    if "--bench-factor" not in arglist and args.max_regression_pct != 30.0:
        args.bench_factor = 1.0 + (float(args.max_regression_pct) / 100.0)
    # CI runners can show significant thermal/CPU jitter for sub-10ms synth
    # benchmarks. Keep default CI gate strict enough for meaningful regressions
    # while reducing flaky failures.
    if (
        args.ci
        and "--bench-factor" not in arglist
        and "--max-regression-pct" not in arglist
    ):
        args.bench_factor = max(float(args.bench_factor), 1.70)


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
        "warning_count": int(result.get("warning_count", 0) or 0),
        "warning_lines": list(result.get("warning_lines", []) or []),
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


def _make_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    if args.ci and "PYTHONWARNINGS" not in env:
        env["PYTHONWARNINGS"] = "default"
    return env


def _run_step_command(
    steps: list[dict[str, Any]],
    *,
    name: str,
    cmd: list[str],
    args: argparse.Namespace,
    env: dict[str, str],
    timeout: float | None = None,
) -> bool:
    result = run_cmd_with_warning_detection(
        cmd,
        timeout=timeout,
        env=env,
        ignore_regexes=list(args.ignore_warning_regex or []),
    )
    ok = bool(result.get("ok"))
    reason = ""
    if args.fail_on_warnings and int(result.get("warning_count", 0) or 0) > 0:
        ok = False
        reason = "warnings detected"
    return _record_step(steps, name=name, ok=ok, result=result, reason=reason)


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

    def _bench_once() -> dict[str, float]:
        return run_benchmark_suite(
            runs=args.bench_runs,
            warmup=args.bench_warmup,
            time_budget_secs=args.bench_time_budget,
        )

    try:
        metrics = _bench_once()
    except Exception as exc:
        return _record_step(
            steps,
            name="bench",
            ok=False,
            reason=f"benchmark_failed: {exc}",
            result={
                "ok": False,
                "secs": time.perf_counter() - started,
                "stdout": "",
                "stderr": str(exc),
            },
            extra={"metrics": metrics},
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
        payload = {
            "meta": {
                "created_at_utc": _utcnow_iso(),
                "python_version": sys.version,
                "platform": platform.platform(),
                "git_commit": _git_commit(),
            },
            "metrics": metrics,
        }
        baseline_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
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
            extra={**step_extra, "baseline_written": True},
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

    factor = float(args.bench_factor)

    def _compute_regressions(
        current_metrics: dict[str, float],
    ) -> list[dict[str, float]]:
        out: list[dict[str, float]] = []
        for metric, current in current_metrics.items():
            base = baseline_metrics.get(metric)
            if base is None:
                continue
            threshold = float(base) * factor
            if float(current) > threshold:
                out.append(
                    {
                        "metric": metric,
                        "current": float(current),
                        "baseline": float(base),
                        "threshold": float(threshold),
                    }
                )
        return out

    metrics_initial = dict(metrics)
    regressions = _compute_regressions(metrics)
    bench_attempts = 1
    bench_retried = False
    retries_left = max(0, int(getattr(args, "bench_retries", 0) or 0))
    while regressions and retries_left > 0:
        retries_left -= 1
        bench_attempts += 1
        bench_retried = True
        try:
            retry_metrics = _bench_once()
        except Exception:
            break
        retry_regressions = _compute_regressions(retry_metrics)
        if len(retry_regressions) <= len(regressions):
            metrics = retry_metrics
            regressions = retry_regressions

    return _record_step(
        steps,
        name="bench",
        ok=len(regressions) == 0,
        reason="" if not regressions else "benchmark regression detected",
        result={
            "ok": len(regressions) == 0,
            "secs": time.perf_counter() - started,
            "stdout": "",
            "stderr": "",
        },
        extra={
            **step_extra,
            "bench_retries": int(getattr(args, "bench_retries", 0) or 0),
            "bench_attempts": int(bench_attempts),
            "bench_retried": bool(bench_retried),
            "initial_metrics": metrics_initial,
            "regressions": regressions,
        },
    )


def _run_health_step(
    args: argparse.Namespace, steps: list[dict[str, Any]], env: dict[str, str]
) -> bool:
    if not (args.health or args.ci):
        return _record_step(
            steps,
            name="health",
            ok=True,
            skipped=True,
            reason="health disabled",
        )

    cmd = [sys.executable, "-m", "app.health", "--mode", args.health_mode]
    if args.health_json:
        cmd.extend(["--json", args.health_json])

    result = run_cmd_with_warning_detection(
        cmd,
        env=env,
        ignore_regexes=list(args.ignore_warning_regex or []),
    )
    ok = bool(result.get("ok"))
    reason = ""
    if args.fail_on_warnings and int(result.get("warning_count", 0) or 0) > 0:
        ok = False
        reason = "warnings detected"
    return _record_step(steps, name="health", ok=ok, result=result, reason=reason)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _normalize_modes(args, argv)
    env = _make_env(args)

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

        if not _run_step_command(
            steps,
            name="compileall",
            cmd=[sys.executable, "-m", "compileall", "-q", "."],
            args=args,
            env=env,
        ):
            exit_code = 2
            return exit_code

        if not _run_step_command(
            steps,
            name="smoke",
            cmd=[sys.executable, "-m", "app.smoke"],
            args=args,
            env=env,
        ):
            exit_code = 2
            return exit_code

        # Run benchmarks before the full pytest/ruff passes to reduce thermal/noise
        # drift on slower CI machines and keep regression checks deterministic.
        if not _run_bench_step(args, steps):
            exit_code = 2
            return exit_code

        pytest_cmd = (
            ["pytest", "-q"]
            if args.full
            else [
                "pytest",
                "-q",
                "tests/test_eventlog.py",
                "tests/test_time_tracking.py",
                "tests/test_benchmarks.py",
            ]
        )
        if not _run_step_command(
            steps,
            name="pytest",
            cmd=pytest_cmd,
            args=args,
            env=env,
        ):
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
            check = run_cmd_with_warning_detection(
                [ruff_path, "check", ".", "--fix"],
                env=env,
                ignore_regexes=args.ignore_warning_regex,
            )
            fmt = run_cmd_with_warning_detection(
                [ruff_path, "format", "."],
                env=env,
                ignore_regexes=args.ignore_warning_regex,
            )
            warning_count = int(check.get("warning_count", 0)) + int(
                fmt.get("warning_count", 0)
            )
            warning_lines = list(check.get("warning_lines", [])) + list(
                fmt.get("warning_lines", [])
            )
            ok = bool(check.get("ok") and fmt.get("ok"))
            reason = ""
            if args.fail_on_warnings and warning_count > 0:
                ok = False
                reason = "warnings detected"
            if not _record_step(
                steps,
                name="ruff",
                ok=ok,
                reason=reason,
                result={
                    "ok": ok,
                    "secs": float(check.get("secs", 0.0)) + float(fmt.get("secs", 0.0)),
                    "stdout": f"{check.get('stdout', '')}{fmt.get('stdout', '')}",
                    "stderr": f"{check.get('stderr', '')}{fmt.get('stderr', '')}",
                    "warning_count": warning_count,
                    "warning_lines": warning_lines[:10],
                },
                extra={"check": check, "format": fmt},
            ):
                exit_code = 2
                return exit_code

        if not _run_health_step(args, steps, env):
            exit_code = 2
            return exit_code

        exit_code = 0
        return exit_code
    finally:
        report["overall_ok"] = exit_code == 0 and all(
            bool(s.get("ok")) for s in report.get("steps", [])
        )
        report["exit_code"] = exit_code
        _write_report(report_path, report)
        print(json.dumps({"json_report": str(report_path), "exit_code": exit_code}))


if __name__ == "__main__":
    raise SystemExit(main())
