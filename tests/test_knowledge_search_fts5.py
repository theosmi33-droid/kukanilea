from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import knowledge_note_create, knowledge_search


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_search_finds_notes_and_respects_limit(tmp_path: Path) -> None:
    _init_core(tmp_path)
    for i in range(5):
        knowledge_note_create(
            "TENANT_A",
            "dev",
            f"Dach Notiz {i}",
            f"Projekt Dach Berlin #{i}",
            "dach,berlin",
        )

    hits = knowledge_search("TENANT_A", "Dach Berlin", limit=3)
    assert 1 <= len(hits) <= 3
    assert all("chunk_id" in h for h in hits)


def test_query_normalization_no_crash_on_operators(tmp_path: Path) -> None:
    _init_core(tmp_path)
    knowledge_note_create("TENANT_A", "dev", "A", "B", "C")
    hits = knowledge_search("TENANT_A", '*** OR "DROP" --', limit=10)
    assert isinstance(hits, list)
