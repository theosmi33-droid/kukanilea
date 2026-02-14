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


def test_claim_and_collision_guard_routes(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    c1 = app.test_client()
    c2 = app.test_client()
    _set_session(c1, user="alice")
    _set_session(c2, user="bob")

    lead_id = _new_lead(c1)

    r_claim = c1.post(f"/api/leads/{lead_id}/claim", json={"ttl_seconds": 900})
    assert r_claim.status_code == 200

    r_claim_b = c2.post(f"/api/leads/{lead_id}/claim", json={"ttl_seconds": 900})
    assert r_claim_b.status_code == 409
    assert ((r_claim_b.get_json() or {}).get("error") or {}).get(
        "code"
    ) == "lead_claimed"

    # collision guard on existing mutating routes
    r_priority = c2.put(
        f"/api/leads/{lead_id}/priority", json={"priority": "high", "pinned": 1}
    )
    assert r_priority.status_code == 409
    assert ((r_priority.get_json() or {}).get("error") or {}).get(
        "code"
    ) == "lead_claimed"

    r_assign = c2.put(f"/api/leads/{lead_id}/assign", json={"assigned_to": "bob"})
    assert r_assign.status_code == 409
    assert ((r_assign.get_json() or {}).get("error") or {}).get(
        "code"
    ) == "lead_claimed"

    r_screen = c2.post(f"/api/leads/{lead_id}/screen/accept", json={})
    assert r_screen.status_code == 409
    assert ((r_screen.get_json() or {}).get("error") or {}).get(
        "code"
    ) == "lead_claimed"

    r_release_fail = c2.post(f"/api/leads/{lead_id}/release", json={})
    assert r_release_fail.status_code == 409

    r_release_ok = c1.post(f"/api/leads/{lead_id}/release", json={})
    assert r_release_ok.status_code == 200


def test_claim_endpoints_read_only_blocked(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)

    client = app.test_client()
    _set_session(client, user="alice")
    lead_id = _new_lead(client)

    app.config["READ_ONLY"] = True

    for url in [
        f"/api/leads/{lead_id}/claim",
        f"/api/leads/{lead_id}/release",
        "/api/leads/claims/expire-now",
    ]:
        resp = client.post(url, json={})
        assert resp.status_code == 403
        payload = resp.get_json() or {}
        assert (payload.get("error_code") == "read_only") or (
            (payload.get("error") or {}).get("code") == "read_only"
        )
