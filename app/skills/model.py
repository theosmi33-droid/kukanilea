from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class SkillFile:
    path: str
    sha256: str
    bytes_len: int


@dataclass
class SkillImportResult:
    name: str
    source_url: str
    ref: str
    resolved_commit: str
    files: Dict[str, bytes] = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
