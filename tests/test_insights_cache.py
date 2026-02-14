from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.insights import get_or_build_daily_insights


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_insights_build_then_cache(tmp_path: Path) -> None:
    _init_core(tmp_path)
    first = get_or_build_daily_insights("TENANT_A", "2026-02-14")
    second = get_or_build_daily_insights("TENANT_A", "2026-02-14")

    assert first["day"] == "2026-02-14"
    assert second["day"] == "2026-02-14"
    assert first["payload"] == second["payload"]
    assert second["cached"] is True
