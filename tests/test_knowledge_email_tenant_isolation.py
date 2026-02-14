from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import knowledge_policy_update, knowledge_search
from app.knowledge.email_source import knowledge_email_ingest_eml


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_email_search_is_tenant_isolated(tmp_path: Path) -> None:
    _init_core(tmp_path)
    knowledge_policy_update(
        "TENANT_A", actor_user_id="dev", allow_customer_pii=True, allow_email=True
    )
    knowledge_policy_update(
        "TENANT_B", actor_user_id="dev", allow_customer_pii=True, allow_email=True
    )

    eml = (
        b"From: a@example.com\nTo: b@example.org\nSubject: Spezieller Suchbegriff\n\n"
        b"Dies ist ein langer genug Text mit Spezieller Suchbegriff fuer den Index."
    )
    knowledge_email_ingest_eml("TENANT_A", "dev", eml, "t.eml")

    a_hits = knowledge_search(
        "TENANT_A", "Spezieller Suchbegriff", source_type="email", limit=10
    )
    b_hits = knowledge_search(
        "TENANT_B", "Spezieller Suchbegriff", source_type="email", limit=10
    )
    assert len(a_hits) >= 1
    assert b_hits == []
