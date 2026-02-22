from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.insights import generate_daily_insights
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.lead_intake.core import lead_claim, leads_assign, leads_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _new_lead(tenant: str, subject: str) -> str:
    return leads_create(
        tenant_id=tenant,
        source="manual",
        contact_name="Alice",
        contact_email="alice@example.com",
        contact_phone="+4912345",
        subject=subject,
        message="Bitte melden",
    )


def test_generate_daily_insights_claim_metrics_and_tenant_isolation(
    tmp_path: Path,
) -> None:
    _init_core(tmp_path)

    lead_a1 = _new_lead("TENANT_A", "A1")
    lead_a2 = _new_lead("TENANT_A", "A2")
    lead_a3 = _new_lead("TENANT_A", "A3")
    lead_b1 = _new_lead("TENANT_B", "B1")

    lead_claim("TENANT_A", lead_a1, actor_user_id="alice", ttl_seconds=600)
    lead_claim("TENANT_A", lead_a3, actor_user_id="alice", ttl_seconds=4000)

    overdue = (datetime.now(UTC) - timedelta(hours=2)).isoformat(
        timespec="seconds"
    )
    leads_assign("TENANT_A", lead_a2, "owner1", overdue, actor_user_id="owner1")
    leads_assign("TENANT_A", lead_a3, "owner1", overdue, actor_user_id="alice")

    with core._DB_LOCK:  # type: ignore[attr-defined]
        con = core._db()  # type: ignore[attr-defined]
        try:
            event_append(
                event_type="lead_claim_collision",
                entity_type="lead",
                entity_id=entity_id_int(lead_a1),
                payload={
                    "schema_version": 1,
                    "source": "test",
                    "actor_user_id": "bob",
                    "tenant_id": "TENANT_A",
                    "data": {
                        "lead_id": lead_a1,
                        "claimed_by_user_id": "alice",
                        "route_key": "lead_priority",
                        "ua_hash": "abc",
                    },
                },
                con=con,
            )
            event_append(
                event_type="lead_claim_collision",
                entity_type="lead",
                entity_id=entity_id_int(lead_b1),
                payload={
                    "schema_version": 1,
                    "source": "test",
                    "actor_user_id": "bob",
                    "tenant_id": "TENANT_B",
                    "data": {
                        "lead_id": lead_b1,
                        "claimed_by_user_id": "x",
                        "route_key": "lead_assign",
                        "ua_hash": "def",
                    },
                },
                con=con,
            )
            con.commit()
        finally:
            con.close()

    payload = generate_daily_insights("TENANT_A", "2026-02-14")

    assert payload["unclaimed_leads_count"] == 1
    assert payload["claims_expiring_soon_count"] == 1
    assert payload["claim_collisions_count"] == 1
    assert payload["leads_overdue_count"] == 2
    assert payload["overdue_leads_by_owner"][0]["owner"] == "owner1"
    assert payload["overdue_leads_by_owner"][0]["count"] == 2
