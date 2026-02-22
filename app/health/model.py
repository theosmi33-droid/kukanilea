from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Severity = Literal["ok", "warn", "fail"]
HealthMode = Literal["ci", "runtime"]


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: Severity
    reason: str | None = None
    remediation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0


@dataclass
class HealthReport:
    ts: datetime
    mode: HealthMode
    ok: bool
    checks: list[CheckResult] = field(default_factory=list)
