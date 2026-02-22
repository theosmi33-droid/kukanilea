from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from app.health.model import CheckResult, HealthMode, HealthReport


class HealthRunner:
    def __init__(
        self,
        mode: HealthMode = "ci",
        strict: bool = False,
        eventlog_limit: int = 200,
        timeout_s: float = 2.0,
    ) -> None:
        self.mode = mode
        self.strict = strict
        self.eventlog_limit = eventlog_limit
        self.timeout_s = timeout_s
        self.checks: list[Callable[[HealthRunner], CheckResult]] = []

    def run(self) -> HealthReport:
        results: list[CheckResult] = []
        overall_ok = True

        ordered_checks = sorted(self.checks, key=lambda fn: getattr(fn, "__name__", ""))
        for check_func in ordered_checks:
            start = time.monotonic()
            try:
                result = check_func(self)
            except Exception as exc:
                duration = time.monotonic() - start
                result = CheckResult(
                    name=getattr(check_func, "__name__", "check"),
                    ok=False,
                    severity="fail",
                    reason=f"Exception: {type(exc).__name__}: {exc}",
                    duration_s=round(duration, 3),
                )
            else:
                duration = time.monotonic() - start
                result.duration_s = round(duration, 3)
                if duration > self.timeout_s:
                    result.ok = False
                    result.severity = "fail" if self.strict else "warn"
                    prefix = (result.reason + "; ") if result.reason else ""
                    result.reason = f"{prefix}timeout"
                    result.details["timeout_s"] = round(self.timeout_s, 3)

            results.append(result)
            if not result.ok:
                overall_ok = False

        return HealthReport(
            ts=datetime.now(UTC),
            mode=self.mode,
            ok=overall_ok,
            checks=results,
        )
