from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.tags.core import (
    tag_assign,
    tag_create,
    tag_delete,
    tag_list,
    tag_unassign,
    tag_update,
    tags_for_entity,
)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_tags_crud_normalization_and_tenant_isolation(tmp_path: Path) -> None:
    _init_core(tmp_path)

    t1 = tag_create("TENANT_A", "Invoice", "#FF00AA", actor_user_id="dev")
    assert t1["name"] == "Invoice"
    assert t1["color"] == "#ff00aa"

    try:
        tag_create("TENANT_A", "invoice", actor_user_id="dev")
    except ValueError as exc:
        assert str(exc) == "duplicate"
    else:
        raise AssertionError("Expected duplicate")

    updated = tag_update("TENANT_A", t1["id"], name="Invoice X", actor_user_id="dev")
    assert updated["name"] == "Invoice X"

    t2 = tag_create("TENANT_B", "Invoice", actor_user_id="dev")
    assert t2["id"] != t1["id"]

    tags_a = tag_list("TENANT_A")
    tags_b = tag_list("TENANT_B")
    assert len(tags_a) == 1
    assert len(tags_b) == 1

    tag_delete("TENANT_A", t1["id"], actor_user_id="dev")
    assert tag_list("TENANT_A") == []


def test_tag_assignment_and_event_payload_pii_safety(tmp_path: Path) -> None:
    _init_core(tmp_path)
    tag = tag_create("TENANT_A", "Urgent", actor_user_id="dev")

    row = tag_assign(
        "TENANT_A",
        entity_type="knowledge_chunk",
        entity_id="chunk-1",
        tag_id=tag["id"],
        actor_user_id="dev",
    )
    assert row["entity_id"] == "chunk-1"

    assigned = tags_for_entity("TENANT_A", "knowledge_chunk", "chunk-1")
    assert len(assigned) == 1

    tag_unassign(
        "TENANT_A",
        entity_type="knowledge_chunk",
        entity_id="chunk-1",
        tag_id=tag["id"],
        actor_user_id="dev",
    )

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT event_type, payload_json
            FROM events
            WHERE event_type LIKE 'tag_%'
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        con.close()

    assert rows
    for r in rows:
        payload = str(r["payload_json"] or "").lower()
        assert '"name"' not in payload
        assert '"email"' not in payload
        assert '"phone"' not in payload


def test_tags_core_read_only_blocks_mutations(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = Flask(__name__)
    app.config["READ_ONLY"] = True
    with app.app_context():
        try:
            tag_create("TENANT_A", "X", actor_user_id="dev")
        except PermissionError as exc:
            assert str(exc) == "read_only"
        else:
            raise AssertionError("Expected read_only")
