from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.autotag import autotag_rule_create
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _iter_keys(data):
    if isinstance(data, dict):
        for k, v in data.items():
            yield str(k)
            yield from _iter_keys(v)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_keys(item)


def test_autotag_related_events_keep_pii_keys_out(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_documents=True,
    )
    autotag_rule_create(
        "TENANT_A",
        name="PII Guard Rule",
        priority=1,
        condition_obj={"type": "filename_glob", "pattern": "*rechnung*"},
        action_list=[{"type": "add_tag", "tag_name": "invoice"}],
        actor_user_id="dev",
    )

    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    fname = "Rechnung_2026-02-15_KD-1234.txt"
    (docs / fname).write_text("content", encoding="utf-8")
    source_watch_config_update("TENANT_A", documents_inbox_dir=str(docs), enabled=True)
    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT event_type, payload_json
            FROM events
            WHERE event_type LIKE 'autotag_%'
               OR event_type LIKE 'source_file_%'
               OR event_type LIKE 'tag_%'
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        con.close()

    assert rows
    forbidden_keys = {"path", "filename", "subject", "email", "phone", "address"}
    for row in rows:
        payload = json.loads(str(row["payload_json"] or "{}"))
        keys = {k.lower() for k in _iter_keys(payload)}
        assert forbidden_keys.isdisjoint(keys)
        payload_text = json.dumps(payload, sort_keys=True).lower()
        assert fname.lower() not in payload_text
        assert str(docs).lower() not in payload_text
