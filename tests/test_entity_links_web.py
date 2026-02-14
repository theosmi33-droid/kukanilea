from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.entity_links.core import list_links_for_entity
from app.knowledge.core import knowledge_note_create
from app.lead_intake.core import leads_create


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
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)
    with app.app_context():
        lead_id = leads_create(
            tenant_id="TENANT_A",
            source="manual",
            contact_name="A",
            contact_email="",
            contact_phone="",
            subject="Lead",
            message="Nachricht",
        )
        note = knowledge_note_create("TENANT_A", "dev", "Titel", "Inhalt", "tag")
    app.config["READ_ONLY"] = bool(read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client, lead_id, str(note["chunk_id"])


def test_entity_links_routes_create_list_delete(tmp_path: Path) -> None:
    client, lead_id, note_id = _client(tmp_path)

    partial = client.get(f"/entity-links/lead/{lead_id}")
    assert partial.status_code == 200

    create_resp = client.post(
        "/entity-links/create",
        data={
            "left_type": "lead",
            "left_id": lead_id,
            "right_type": "knowledge_note",
            "right_id": note_id,
            "link_type": "related",
            "context_entity_type": "lead",
            "context_entity_id": lead_id,
        },
    )
    assert create_resp.status_code == 200

    links = list_links_for_entity("TENANT_A", "lead", lead_id)
    assert len(links) == 1
    link_id = links[0]["id"]

    delete_resp = client.post(
        f"/entity-links/{link_id}/delete",
        data={"context_entity_type": "lead", "context_entity_id": lead_id},
    )
    assert delete_resp.status_code == 200
    assert list_links_for_entity("TENANT_A", "lead", lead_id) == []


def test_entity_links_read_only_returns_403(tmp_path: Path) -> None:
    client, lead_id, note_id = _client(tmp_path, read_only=True)
    resp = client.post(
        "/entity-links/create",
        data={
            "left_type": "lead",
            "left_id": lead_id,
            "right_type": "knowledge_note",
            "right_id": note_id,
            "link_type": "related",
        },
    )
    assert resp.status_code == 403
