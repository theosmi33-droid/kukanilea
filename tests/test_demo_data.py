from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.demo_data import generate_demo_data


def _init_core(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    core.DB_PATH = db_path
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    return db_path


def test_generate_demo_data_creates_expected_counts(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "demo-test-anon")

    summary = generate_demo_data(db_path=db_path, tenant_id="TENANT_X")

    assert int(summary["customers"]) == 5
    assert int(summary["contacts"]) == 5
    assert int(summary["leads"]) == 1
    assert int(summary["tasks"]) == 3
    assert int(summary["documents"]) == 10
    assert int(summary["automation_rules"]) == 1
