from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

Severity = Literal["ok", "warn", "fail"]
HealthMode = Literal["ci", "runtime"]


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: Severity
    reason: Optional[str] = None
    remediation: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0


@dataclass
class HealthReport:
    ts: datetime
    mode: HealthMode
    ok: bool
    checks: List[CheckResult] = field(default_factory=list)
