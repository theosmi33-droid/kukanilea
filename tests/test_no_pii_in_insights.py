from __future__ import annotations

import json
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.insights import generate_daily_insights
from app.lead_intake.core import leads_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_daily_insights_payload_excludes_lead_pii_fields(tmp_path: Path) -> None:
    _init_core(tmp_path)
    secret_subject = "Top Secret Dachinspektion"
    secret_message = "Bitte sende Angebot an alice@example.com oder +49 170 1234567"

    leads_create(
        tenant_id="TENANT_A",
        source="manual",
        contact_name="Alice",
        contact_email="alice@example.com",
        contact_phone="+491701234567",
        subject=secret_subject,
        message=secret_message,
    )

    payload = generate_daily_insights("TENANT_A", "2026-02-14")
    blob = json.dumps(payload, sort_keys=True)

    assert "alice@example.com" not in blob
    assert "+491701234567" not in blob
    assert secret_subject not in blob
    assert secret_message not in blob
    assert "message" not in blob
    assert "contact_email" not in blob
    assert "contact_phone" not in blob
