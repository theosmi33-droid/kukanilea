from __future__ import annotations

from datetime import UTC, datetime

from app.health.cli import report_to_jsonable
from app.health.core import HealthRunner
from app.health.model import CheckResult, HealthReport


def test_health_runner_order_is_deterministic_alphabetical() -> None:
    runner = HealthRunner(mode="ci", strict=False, timeout_s=5.0)

    def check_z(_runner):
        return CheckResult(name="z", ok=True, severity="ok")

    def check_a(_runner):
        return CheckResult(name="a", ok=True, severity="ok")

    runner.checks = [check_z, check_a]
    report = runner.run()

    assert [c.name for c in report.checks] == ["a", "z"]


def test_health_json_is_stable_and_masks_tmp_paths() -> None:
    report = HealthReport(
        ts=datetime(2026, 1, 1, tzinfo=UTC),
        mode="ci",
        ok=False,
        checks=[
            CheckResult(
                name="x",
                ok=False,
                severity="warn",
                reason="path /tmp/random/file",
                details={"p": "/var/folders/abc/test"},
                duration_s=0.123456,
            )
        ],
    )

    data = report_to_jsonable(report)
    dumped = str(data)
    assert "/tmp" not in dumped
    assert "/var/folders" not in dumped
    assert "<tmp>" in dumped
    assert data["checks"][0]["duration_s"] == 0.123
