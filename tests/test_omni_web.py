from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.omni.hub import ingest_fixture

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eml" / "sample_with_pii.eml"


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path):
    _init_core(tmp_path)
    result = ingest_fixture(
        "TENANT_A",
        channel="email",
        fixture_path=FIXTURE,
        dry_run=False,
        actor_user_id="dev",
    )
    event_id = result["results"][0]["event_id"]
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client, event_id


def test_conversations_pages_render(tmp_path: Path) -> None:
    client, event_id = _client(tmp_path)
    list_resp = client.get("/conversations")
    assert list_resp.status_code == 200
    assert b"Conversations" in list_resp.data

    detail_resp = client.get(f"/conversations/{event_id}")
    assert detail_resp.status_code == 200
    assert b"Redacted Payload" in detail_resp.data


def test_conversations_tenant_isolation(tmp_path: Path) -> None:
    client, event_id = _client(tmp_path)
    with client.session_transaction() as sess:
        sess["tenant_id"] = "TENANT_B"
    resp = client.get(f"/conversations/{event_id}")
    assert resp.status_code == 404
