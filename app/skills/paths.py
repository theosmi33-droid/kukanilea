from __future__ import annotations

import os
from pathlib import Path

from app.config import Config
from app.skills.util import ensure_dir


def _user_data_root() -> Path:
    env = os.environ.get("KUKANILEA_USER_DATA_ROOT")
    if env:
        return ensure_dir(Path(env))
    return ensure_dir(Path(Config.USER_DATA_ROOT))


def skills_root() -> Path:
    return ensure_dir(_user_data_root() / "skills")


def cache_root() -> Path:
    return ensure_dir(skills_root() / "cache")


def quarantine_root() -> Path:
    return ensure_dir(skills_root() / "quarantine")


def active_root() -> Path:
    return ensure_dir(skills_root() / "active")
