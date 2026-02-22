from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SkillSource:
    host: str
    org: str
    repo: str
    ref: str
    base_path: str = "skills"


@dataclass
class FetchedSkill:
    skill_name: str
    ref: str
    files: dict[str, bytes] = field(default_factory=dict)
    fetched_from_urls: dict[str, str] = field(default_factory=dict)
    content_sha256: dict[str, str] = field(default_factory=dict)
