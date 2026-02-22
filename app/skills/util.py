from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

_ALLOWED_SKILL = re.compile(r"^[A-Za-z0-9_-]+$")


def sanitize_skill_name(name: str) -> str:
    value = (name or "").strip()
    if not value or not _ALLOWED_SKILL.match(value):
        raise ValueError("invalid_skill_name")
    return value


def sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_join(base: Path, rel: str) -> Path:
    rel_path = Path(rel)
    if rel_path.is_absolute():
        raise ValueError("unsafe_relative_path")
    joined = (base / rel_path).resolve()
    base_resolved = base.resolve()
    if not str(joined).startswith(str(base_resolved)):
        raise ValueError("unsafe_relative_path")
    return joined
