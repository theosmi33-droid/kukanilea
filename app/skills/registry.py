from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core import logic as core
from app.eventlog.core import event_append
from app.skills.paths import active_root
from app.skills.util import utcnow_iso

_ALLOWED_STATUS = {"quarantine", "active"}


def _connect() -> sqlite3.Connection:
    core.db_init()
    db_path = Path(core.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _event_payload(
    source: str, actor_user_id: int | None, data: dict[str, Any]
) -> dict:
    return {
        "schema_version": 1,
        "source": source,
        "actor_user_id": actor_user_id,
        "data": data,
    }


def register_skill(
    cache_key: str,
    name: str,
    source_url: str,
    ref: str,
    resolved_commit: str,
    fetched_at_utc: str,
    manifest_dict: dict,
    status: str = "quarantine",
    *,
    actor_user_id: int | None = None,
) -> int:
    status_norm = (status or "quarantine").strip().lower()
    if status_norm not in _ALLOWED_STATUS:
        raise ValueError("invalid_status")

    with _connect() as con:
        cur = con.execute(
            """
            INSERT INTO skills(
              cache_key, name, source_url, ref, resolved_commit, status, fetched_at, manifest_json
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                cache_key,
                name,
                source_url,
                ref,
                resolved_commit,
                status_norm,
                fetched_at_utc,
                json.dumps(manifest_dict, ensure_ascii=False, sort_keys=True),
            ),
        )
        skill_id = int(cur.lastrowid or 0)
        event_append(
            "skill_fetched",
            "skill",
            skill_id,
            _event_payload(
                "skills/register",
                actor_user_id,
                {
                    "cache_key": cache_key,
                    "name": name,
                    "source_url": source_url,
                    "ref": ref,
                    "resolved_commit": resolved_commit,
                    "status": status_norm,
                },
            ),
            con=con,
        )
        con.commit()
        return skill_id


def list_skills() -> list[dict]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT id, cache_key, name, status, source_url, resolved_commit, fetched_at
            FROM skills
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def _get_skill(con: sqlite3.Connection, skill_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM skills WHERE id=?", (int(skill_id),)).fetchone()
    if not row:
        raise ValueError("skill_not_found")
    return row


def activate_skill(skill_id: int, *, actor_user_id: int | None = None) -> dict:
    with _connect() as con:
        row = _get_skill(con, int(skill_id))
        con.execute("UPDATE skills SET status=? WHERE id=?", ("active", int(skill_id)))

        manifest = json.loads(str(row["manifest_json"] or "{}"))
        cache_key = str(row["cache_key"])
        cache_folder = str(manifest.get("cache_folder") or "")
        link_path = active_root() / f"{cache_key}.link"
        link_payload = {
            "skill_id": int(skill_id),
            "cache_key": cache_key,
            "path": cache_folder,
            "activated_at_utc": utcnow_iso(),
        }
        link_path.write_text(json.dumps(link_payload, indent=2, sort_keys=True) + "\n")

        event_append(
            "skill_activated",
            "skill",
            int(skill_id),
            _event_payload(
                "skills/activate",
                actor_user_id,
                {"cache_key": cache_key, "path": cache_folder},
            ),
            con=con,
        )
        con.commit()
        return link_payload


def quarantine_skill(skill_id: int, *, actor_user_id: int | None = None) -> None:
    with _connect() as con:
        row = _get_skill(con, int(skill_id))
        con.execute(
            "UPDATE skills SET status=? WHERE id=?", ("quarantine", int(skill_id))
        )
        cache_key = str(row["cache_key"])
        link_path = active_root() / f"{cache_key}.link"
        if link_path.exists():
            link_path.unlink()
        event_append(
            "skill_quarantined",
            "skill",
            int(skill_id),
            _event_payload(
                "skills/quarantine", actor_user_id, {"cache_key": cache_key}
            ),
            con=con,
        )
        con.commit()
