from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.config import Config
from app.devtools.conversation_scenarios import run_scenario


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_scenario_email_with_pii(tmp_path: Path) -> None:
    _init_core(tmp_path)
    old_core = Config.CORE_DB
    Config.CORE_DB = core.DB_PATH
    try:
        report = run_scenario("TENANT_A", "email_with_pii")
    finally:
        Config.CORE_DB = old_core
    assert report["ok"] is True
    assert "pii_redacted" in report["invariants_passed"]


def test_scenario_two_tenants(tmp_path: Path) -> None:
    _init_core(tmp_path)
    old_core = Config.CORE_DB
    Config.CORE_DB = core.DB_PATH
    try:
        report = run_scenario("TENANT_A", "two_tenants")
    finally:
        Config.CORE_DB = old_core
    assert report["ok"] is True
    assert "tenant_isolation" in report["invariants_passed"]


def test_scenario_unknown() -> None:
    report = run_scenario("TENANT_A", "unknown")
    assert report["ok"] is False
    assert "unknown_scenario" in report["reasons"]
