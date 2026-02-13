from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.skills.registry import activate_skill, quarantine_skill, register_skill


def _init_core(tmp_path: Path) -> Path:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    return Path(core.DB_PATH)


def test_register_activate_quarantine_writes_events(tmp_path: Path) -> None:
    db = _init_core(tmp_path)
    cache_folder = tmp_path / "cache" / "demo_key"
    cache_folder.mkdir(parents=True, exist_ok=True)

    manifest = {
        "meta": {"cache_key": "demo_key", "status": "quarantine"},
        "cache_folder": str(cache_folder),
        "files": [{"path": "skills/demo/SKILL.md", "sha256": "abc", "bytes_len": 10}],
    }

    skill_id = register_skill(
        cache_key="demo_key",
        name="demo",
        source_url="https://github.com/acme/repo",
        ref="main",
        resolved_commit="d" * 40,
        fetched_at_utc="2026-02-13T10:00:00+00:00",
        manifest_dict=manifest,
        actor_user_id=7,
    )
    assert skill_id > 0

    pointer = activate_skill(skill_id, actor_user_id=7)
    assert pointer["skill_id"] == skill_id

    quarantine_skill(skill_id, actor_user_id=7)

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        status_row = con.execute(
            "SELECT status FROM skills WHERE id=?", (skill_id,)
        ).fetchone()
        assert status_row is not None
        assert status_row["status"] == "quarantine"

        events = con.execute(
            "SELECT event_type, payload_json FROM events WHERE entity_type='skill' AND entity_id=? ORDER BY id",
            (skill_id,),
        ).fetchall()
        assert [e["event_type"] for e in events] == [
            "skill_fetched",
            "skill_activated",
            "skill_quarantined",
        ]
        payload = json.loads(events[0]["payload_json"])
        assert payload["schema_version"] == 1
        assert payload["actor_user_id"] == 7
    finally:
        con.close()
