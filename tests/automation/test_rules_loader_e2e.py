from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.event_id_map import entity_id_int
from app.eventlog.core import GENESIS_HASH, event_hash
from app.modules.automation import (
    builder_execution_log_list,
    load_rule_file,
    load_rules_from_dir,
    process_cron_for_tenant,
    process_events_for_tenant,
)


def _append_event(*, db_path: Path, event_type: str, payload: dict, entity_ref: str) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              event_type TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              prev_hash TEXT NOT NULL,
              hash TEXT NOT NULL UNIQUE
            )
            """
        )
        row = con.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
        prev = str(row[0]) if row else GENESIS_HASH
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        hsh = event_hash(prev, ts, event_type, "automation_test", entity_id_int(entity_ref), payload_json)
        cur = con.execute(
            """
            INSERT INTO events(ts,event_type,entity_type,entity_id,payload_json,prev_hash,hash)
            VALUES (?,?,?,?,?,?,?)
            """,
            (ts, event_type, "automation_test", entity_id_int(entity_ref), payload_json, prev, hsh),
        )
        con.commit()
        return int(cur.lastrowid or 0)
    finally:
        con.close()


def test_load_rule_file_accepts_yaml_extension_with_json_content():
    path = Path("app/modules/automation/examples/02_case_ack.yaml")
    doc = load_rule_file(path)
    assert doc["name"] == "Case acknowledgement"
    assert len(doc["triggers"]) == 1


def test_example_rules_run_end_to_end(tmp_path):
    db_path = tmp_path / "core.sqlite3"

    tenant_id = "KUKANILEA"
    created = load_rules_from_dir(
        tenant_id=tenant_id,
        rules_dir=Path("app/modules/automation/examples"),
        db_path=db_path,
    )
    assert len(created) == 5

    _append_event(db_path=db_path, event_type="lead.created", entity_ref="lead-1", payload={"tenant_id": tenant_id, "lead_id": "L-100"})
    _append_event(db_path=db_path, event_type="case.opened", entity_ref="case-1", payload={"tenant_id": tenant_id, "case_id": "C-100"})
    _append_event(db_path=db_path, event_type="task.completed", entity_ref="task-1", payload={"tenant_id": tenant_id, "task_status": "done"})
    _append_event(db_path=db_path, event_type="intent.detected", entity_ref="intent-1", payload={"tenant_id": tenant_id, "intent": "needs_followup"})

    event_result = process_events_for_tenant(tenant_id=tenant_id, db_path=db_path)
    assert event_result["ok"] is True
    assert event_result["matched"] == 4

    cron_result = process_cron_for_tenant(
        tenant_id=tenant_id,
        db_path=db_path,
        now_dt=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
    )
    assert cron_result["ok"] is True
    assert cron_result["matched"] == 1

    logs = builder_execution_log_list(tenant_id=tenant_id, db_path=db_path, limit=20)
    assert len(logs) >= 5
