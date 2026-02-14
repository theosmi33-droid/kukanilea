from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import (
    knowledge_note_create,
    knowledge_notes_list,
    knowledge_search,
)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_tenant_isolation_for_list_and_search(tmp_path: Path) -> None:
    _init_core(tmp_path)
    knowledge_note_create("TENANT_A", "dev", "Alpha", "Nur A", "a")
    knowledge_note_create("TENANT_B", "dev", "Beta", "Nur B", "b")

    a_list = knowledge_notes_list("TENANT_A", owner_user_id="dev", limit=20, offset=0)
    b_list = knowledge_notes_list("TENANT_B", owner_user_id="dev", limit=20, offset=0)
    assert any("Alpha" in str(r.get("title") or "") for r in a_list)
    assert not any("Beta" in str(r.get("title") or "") for r in a_list)
    assert any("Beta" in str(r.get("title") or "") for r in b_list)

    a_hits = knowledge_search("TENANT_A", "Beta", limit=10)
    assert a_hits == []
