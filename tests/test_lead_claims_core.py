from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import kukanilea_core_v3_fixed as core
from app.lead_intake.core import (
    ConflictError,
    lead_claim,
    lead_claim_get,
    lead_claims_auto_expire,
    lead_release_claim,
    leads_create,
)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _new_lead(tenant: str = "TENANT_A") -> str:
    return leads_create(
        tenant_id=tenant,
        source="manual",
        contact_name="A",
        contact_email="a@example.com",
        contact_phone="",
        subject="Lead",
        message="M",
    )


def test_claim_release_force_and_tenant_isolation(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id = _new_lead("TENANT_A")

    c1 = lead_claim("TENANT_A", lead_id, actor_user_id="alice", ttl_seconds=900)
    assert c1["active"] is True
    assert c1["claimed_by"] == "alice"

    with pytest.raises(ConflictError) as e1:
        lead_claim("TENANT_A", lead_id, actor_user_id="bob", ttl_seconds=900)
    assert str(e1.value) == "lead_claimed"

    c2 = lead_claim(
        "TENANT_A", lead_id, actor_user_id="bob", ttl_seconds=900, force=True
    )
    assert c2["active"] is True
    assert c2["claimed_by"] == "bob"

    with pytest.raises(ConflictError) as e2:
        lead_release_claim("TENANT_A", lead_id, actor_user_id="alice")
    assert str(e2.value) == "not_owner"

    lead_release_claim("TENANT_A", lead_id, actor_user_id="bob")
    c3 = lead_claim_get("TENANT_A", lead_id)
    assert c3 is not None
    assert c3["active"] is False
    assert c3["released_at"] is not None

    # tenant isolation
    assert lead_claim_get("TENANT_B", lead_id) is None


def test_auto_expire_updates_claim_and_writes_events(tmp_path: Path) -> None:
    _init_core(tmp_path)
    lead_id = _new_lead("TENANT_A")
    lead_claim("TENANT_A", lead_id, actor_user_id="alice", ttl_seconds=900)

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            "UPDATE lead_claims SET claimed_until='2000-01-01T00:00:00+00:00' WHERE tenant_id=? AND lead_id=?",
            ("TENANT_A", lead_id),
        )
        con.commit()
    finally:
        con.close()

    expired = lead_claims_auto_expire("TENANT_A", max_actions=10, actor_user_id="ops")
    assert expired == 1

    claim = lead_claim_get("TENANT_A", lead_id)
    assert claim is not None
    assert claim["active"] is False
    assert claim["release_reason"] == "expired"

    con2 = sqlite3.connect(str(core.DB_PATH))
    con2.row_factory = sqlite3.Row
    try:
        ev = con2.execute(
            "SELECT event_type FROM events WHERE event_type='lead_claim_expired' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert ev is not None
    finally:
        con2.close()
