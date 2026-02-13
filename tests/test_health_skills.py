from __future__ import annotations

import builtins
from pathlib import Path

from app.config import Config
from app.health.checks import check_db_access, check_skills_registry
from app.health.core import HealthRunner


def test_health_skills_runtime_read_only_warns_when_missing(
    tmp_path: Path, monkeypatch
) -> None:
    user_root = tmp_path / "user_data"
    monkeypatch.setattr(Config, "USER_DATA_ROOT", user_root)

    write_calls = {"mkdir": 0, "write_text": 0, "open_w": 0}

    orig_mkdir = Path.mkdir
    orig_write_text = Path.write_text
    orig_open = builtins.open

    def fail_mkdir(self, *args, **kwargs):
        write_calls["mkdir"] += 1
        raise AssertionError("mkdir should not be called in runtime mode")

    def fail_write_text(self, *args, **kwargs):
        write_calls["write_text"] += 1
        raise AssertionError("write_text should not be called in runtime mode")

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "+")):
            write_calls["open_w"] += 1
            raise AssertionError("open for write should not be called in runtime mode")
        return orig_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)
    monkeypatch.setattr(Path, "write_text", fail_write_text)
    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Config, "CORE_DB", user_root / "missing.db")

    runner = HealthRunner(mode="runtime", strict=False)
    result_skills = check_skills_registry(runner)
    result_db = check_db_access(runner)

    assert result_skills.ok is False
    assert result_skills.severity == "warn"
    assert result_db.ok is False
    assert result_db.severity == "warn"
    assert write_calls == {"mkdir": 0, "write_text": 0, "open_w": 0}

    monkeypatch.setattr(Path, "mkdir", orig_mkdir)
    monkeypatch.setattr(Path, "write_text", orig_write_text)
    monkeypatch.setattr(builtins, "open", orig_open)
