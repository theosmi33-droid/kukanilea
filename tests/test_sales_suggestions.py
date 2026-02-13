from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.sales import deals_suggest_next_actions


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_suggestions_are_gated(monkeypatch, tmp_path: Path) -> None:
    _init_core(tmp_path)
    customer_id = core.customers_create("TENANT_A", "Sales Kunde")
    deal_id = core.deals_create(
        tenant_id="TENANT_A",
        customer_id=customer_id,
        title="Lead",
        stage="lead",
    )

    monkeypatch.delenv("KUKA_AI_ENABLE", raising=False)
    assert deals_suggest_next_actions("TENANT_A", deal_id) == []

    monkeypatch.setenv("KUKA_AI_ENABLE", "1")
    suggestions = deals_suggest_next_actions("TENANT_A", deal_id)
    assert suggestions
    assert suggestions[0]["action"] == "qualify_deal"
