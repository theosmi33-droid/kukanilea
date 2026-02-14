from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.entity_links.core import create_link, delete_link, list_links_for_entity
from app.knowledge.core import knowledge_note_create
from app.lead_intake.core import leads_create

PII_KEYS = ["email", "phone", "subject", "message", "notes", "body", "contact_"]


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _seed_entities() -> tuple[str, str]:
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
    return lead_id, str(note["chunk_id"])


def test_create_link_canonical_and_duplicate_symmetry(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id, note_id = _seed_entities()

    row = create_link(
        "TENANT_A",
        "lead",
        lead_id,
        "knowledge_note",
        note_id,
        "related",
        actor_user_id="dev",
    )
    assert row["id"]

    try:
        create_link(
            "TENANT_A",
            "knowledge_note",
            note_id,
            "lead",
            lead_id,
            "related",
            actor_user_id="dev",
        )
        assert False, "expected duplicate"
    except ValueError as exc:
        assert str(exc) == "duplicate"


def test_self_link_rejected(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id, _ = _seed_entities()
    try:
        create_link("TENANT_A", "lead", lead_id, "lead", lead_id, "related")
        assert False, "expected validation_error"
    except ValueError as exc:
        assert str(exc) == "validation_error"


def test_tenant_isolation_and_event_payload_no_pii(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id, note_id = _seed_entities()
    row = create_link(
        "TENANT_A",
        "lead",
        lead_id,
        "knowledge_note",
        note_id,
        "references",
        actor_user_id="dev",
    )

    a_rows = list_links_for_entity("TENANT_A", "lead", lead_id)
    b_rows = list_links_for_entity("TENANT_B", "lead", lead_id)
    assert len(a_rows) == 1
    assert b_rows == []

    delete_link("TENANT_A", row["id"], actor_user_id="dev")

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        evs = con.execute(
            "SELECT event_type, payload_json FROM events WHERE event_type IN ('entity_link_created','entity_link_deleted') ORDER BY id ASC"
        ).fetchall()
        assert len(evs) == 2
        for ev in evs:
            payload = json.loads(str(ev["payload_json"]))
            payload_text = json.dumps(payload, sort_keys=True)
            for key in PII_KEYS:
                assert key not in payload_text
    finally:
        con.close()


def test_read_only_blocks_core_mutations(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id, note_id = _seed_entities()
    app = Flask(__name__)
    app.config["READ_ONLY"] = True
    with app.app_context():
        try:
            create_link(
                "TENANT_A", "lead", lead_id, "knowledge_note", note_id, "related"
            )
            assert False, "expected read_only"
        except PermissionError as exc:
            assert str(exc) == "read_only"
