from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.knowledge.core import knowledge_note_create
from app.tags.core import tag_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path, read_only: bool = False):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_tags_page_and_assign_unassign_flow(tmp_path: Path) -> None:
    client = _client(tmp_path)
    note = knowledge_note_create("TENANT_A", "dev", "N1", "Body", "a")
    tag = tag_create("TENANT_A", "Alpha", actor_user_id="dev")

    page = client.get("/tags")
    assert page.status_code == 200
    assert b"Globale Tags" in page.data

    assign = client.post(
        "/tags/assign",
        data={
            "entity_type": "knowledge_chunk",
            "entity_id": note["chunk_id"],
            "tag_id": tag["id"],
        },
    )
    assert assign.status_code == 200

    unassign = client.post(
        "/tags/unassign",
        data={
            "entity_type": "knowledge_chunk",
            "entity_id": note["chunk_id"],
            "tag_id": tag["id"],
        },
    )
    assert unassign.status_code == 200


def test_tags_read_only_blocked(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)

    resp = client.post(
        "/tags/create",
        data={"name": "Blocked", "color": "#112233"},
    )
    assert resp.status_code == 403
