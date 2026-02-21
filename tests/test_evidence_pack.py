from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.config import Config
from app.entity_links import create_link
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import knowledge_note_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path):
    _init_core(tmp_path)
    Config.CORE_DB = core.DB_PATH
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", CORE_DB=core.DB_PATH)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def _create_lead(client) -> str:
    created = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "Alice",
            "subject": "Dachreparatur",
            "message": "Bitte melden",
        },
    )
    assert created.status_code == 200
    lead_id = (created.get_json() or {}).get("lead_id")
    assert lead_id
    return str(lead_id)


def test_evidence_pack_requires_auth(tmp_path: Path) -> None:
    _init_core(tmp_path)
    Config.CORE_DB = core.DB_PATH
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", CORE_DB=core.DB_PATH)
    client = app.test_client()
    resp = client.get("/api/reports/evidence-pack/abc?entity_type=lead")
    assert resp.status_code == 401


def test_evidence_pack_lead_includes_request_ids_and_attachments(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    lead_id = _create_lead(client)

    event_append(
        event_type="lead_note_added",
        entity_type="lead",
        entity_id=entity_id_int(lead_id),
        payload={
            "tenant_id": "TENANT_A",
            "request_id": "req-evidence-1",
            "data": {"lead_id": lead_id},
        },
    )

    note = knowledge_note_create(
        tenant_id="TENANT_A",
        owner_user_id="dev",
        title="Beleg",
        body="Foto und Notiz",
    )
    create_link(
        tenant_id="TENANT_A",
        left_type="lead",
        left_id=lead_id,
        right_type="knowledge_note",
        right_id=str(note["chunk_id"]),
        link_type="attachment",
        actor_user_id="dev",
    )

    resp = client.get(f"/api/reports/evidence-pack/{lead_id}?entity_type=lead")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    pack = payload.get("evidence_pack") or {}
    assert payload.get("ok") is True
    assert pack.get("entity_type") == "lead"
    assert str(pack.get("entity_id") or "") == lead_id
    assert "req-evidence-1" in (pack.get("request_ids") or [])
    attachments = pack.get("attachments") or []
    assert any(
        str(a.get("entity_type") or "") == "knowledge_note"
        and str(a.get("entity_id") or "") == str(note["chunk_id"])
        for a in attachments
    )


def test_evidence_pack_tenant_isolation(tmp_path: Path) -> None:
    client = _client(tmp_path)
    lead_id = _create_lead(client)
    with client.session_transaction() as sess:
        sess["tenant_id"] = "TENANT_B"
    resp = client.get(f"/api/reports/evidence-pack/{lead_id}?entity_type=lead")
    assert resp.status_code == 404


def test_evidence_pack_validation_error(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.get("/api/reports/evidence-pack/abc?entity_type=invalid")
    assert resp.status_code == 400
    payload = resp.get_json() or {}
    assert (payload.get("error") or {}).get("code") == "validation_error"
