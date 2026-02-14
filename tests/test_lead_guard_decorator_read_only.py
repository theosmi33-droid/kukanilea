from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _set_session(client, *, user: str, tenant: str = "TENANT_A") -> None:
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = tenant


def _new_lead(client) -> str:
    resp = client.post(
        "/api/leads",
        json={
            "source": "manual",
            "contact_name": "Alice",
            "subject": "Dach",
            "message": "Bitte melden",
        },
    )
    assert resp.status_code == 200
    lead_id = (resp.get_json() or {}).get("lead_id")
    assert lead_id
    return lead_id


def test_guard_blocks_mutations_in_read_only_mode(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    client = app.test_client()
    _set_session(client, user="alice")
    lead_id = _new_lead(client)

    app.config["READ_ONLY"] = True

    resp = client.put(
        f"/api/leads/{lead_id}/priority", json={"priority": "high", "pinned": 1}
    )
    assert resp.status_code == 403
    payload = resp.get_json() or {}
    assert (payload.get("error_code") == "read_only") or (
        (payload.get("error") or {}).get("code") == "read_only"
    )
