from __future__ import annotations

from pathlib import Path

from app.config import Config
from app.health.checks import check_skills_registry
from app.health.core import HealthRunner


def test_health_skills_runtime_read_only_warns_when_missing(
    tmp_path: Path, monkeypatch
) -> None:
    user_root = tmp_path / "user_data"
    monkeypatch.setattr(Config, "USER_DATA_ROOT", user_root)

    runner = HealthRunner(mode="runtime", strict=False)
    result = check_skills_registry(runner)

    assert result.ok is False
    assert result.severity == "warn"
    assert not (user_root / "skills").exists()
