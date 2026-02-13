from __future__ import annotations

from app.health.checks import check_eventlog_chain
from app.health.core import HealthRunner


def test_health_eventlog_chain_ci_ok() -> None:
    runner = HealthRunner(mode="ci", strict=True, eventlog_limit=10)
    result = check_eventlog_chain(runner)
    assert result.ok is True
    assert result.severity == "ok"
