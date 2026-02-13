from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, List

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
        self.checks: List[Callable[["HealthRunner"], CheckResult]] = []

    def run(self) -> HealthReport:
        results: list[CheckResult] = []
        overall_ok = True
        for check_func in self.checks:
            start = time.monotonic()
            try:
                result = check_func(self)
            except Exception as exc:
                duration = time.monotonic() - start
                result = CheckResult(
                    name=check_func.__name__,
                    ok=False,
                    severity="fail",
                    reason=f"Exception: {type(exc).__name__}: {exc}",
                    duration_s=duration,
                )
            else:
                duration = time.monotonic() - start
                result.duration_s = duration
                if duration > self.timeout_s:
                    result.ok = False
                    result.severity = "fail" if self.strict else "warn"
                    prefix = (result.reason + "; ") if result.reason else ""
                    result.reason = f"{prefix}timeout after {duration:.2f}s"
                    result.details["timeout_s"] = self.timeout_s

            results.append(result)
            if not result.ok:
                overall_ok = False

        return HealthReport(
            ts=datetime.now(timezone.utc),
            mode=self.mode,
            ok=overall_ok,
            checks=results,
        )
