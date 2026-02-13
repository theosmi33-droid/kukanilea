from __future__ import annotations

from app.health.core import HealthRunner
from app.health.model import CheckResult


def test_health_runner_order_and_overall_ok() -> None:
    runner = HealthRunner(mode="ci", strict=False, timeout_s=5.0)

    def check_a(_runner):
        return CheckResult(name="a", ok=True, severity="ok")

    def check_b(_runner):
        return CheckResult(name="b", ok=False, severity="warn", reason="warn")

    runner.checks = [check_a, check_b]
    report = runner.run()

    assert [c.name for c in report.checks] == ["a", "b"]
    assert report.ok is False


def test_health_runner_timeout_marks_warn_or_fail() -> None:
    runner = HealthRunner(mode="ci", strict=False, timeout_s=0.00001)

    def check_slow(_runner):
        value = 0
        for i in range(20000):
            value += i
        return CheckResult(name="slow", ok=True, severity="ok", details={"v": value})

    runner.checks = [check_slow]
    report = runner.run()
    assert report.checks[0].ok is False
    assert report.checks[0].severity in {"warn", "fail"}

    strict_runner = HealthRunner(mode="ci", strict=True, timeout_s=0.00001)
    strict_runner.checks = [check_slow]
    strict_report = strict_runner.run()
    assert strict_report.checks[0].severity == "fail"
