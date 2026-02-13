from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from flask import current_app, has_app_context

from app.config import Config

GENESIS_HASH = "0" * 64


def _core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _connect() -> sqlite3.Connection:
    db = _core_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stable_payload_json(payload: Dict[str, Any]) -> str:
    return json.dumps(
        payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def ensure_eventlog_schema() -> None:
    con = _connect()
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
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_type, entity_id, id DESC)"
        )
        con.commit()
    finally:
        con.close()


def event_hash(
    prev_hash: str,
    ts: str,
    event_type: str,
    entity_type: str,
    entity_id: int,
    payload_json: str,
) -> str:
    raw = "|".join(
        [
            str(prev_hash or ""),
            str(ts or ""),
            str(event_type or ""),
            str(entity_type or ""),
            str(int(entity_id)),
            str(payload_json or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def event_append(
    event_type: str,
    entity_type: str,
    entity_id: int,
    payload: Dict[str, Any],
    *,
    con: sqlite3.Connection | None = None,
) -> int:
    if con is None:
        ensure_eventlog_schema()
    ev_type = (event_type or "").strip()
    ent_type = (entity_type or "").strip()
    ent_id = int(entity_id)
    if not ev_type or not ent_type or ent_id <= 0:
        raise ValueError("invalid_event")

    ts = _now_iso()
    payload_json = _stable_payload_json(payload)

    owns_connection = con is None
    db = con or _connect()
    try:
        if owns_connection:
            db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
        prev = str(row["hash"]) if row else GENESIS_HASH
        hsh = event_hash(prev, ts, ev_type, ent_type, ent_id, payload_json)
        cur = db.execute(
            """
            INSERT INTO events(ts, event_type, entity_type, entity_id, payload_json, prev_hash, hash)
            VALUES (?,?,?,?,?,?,?)
            """,
            (ts, ev_type, ent_type, ent_id, payload_json, prev, hsh),
        )
        if owns_connection:
            db.commit()
        return int(cur.lastrowid or 0)
    finally:
        if owns_connection:
            db.close()


def event_verify_chain() -> Tuple[bool, Optional[int], Optional[str]]:
    ensure_eventlog_schema()
    con = _connect()
    try:
        rows = con.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
    finally:
        con.close()

    prev = GENESIS_HASH
    for row in rows:
        rid = int(row["id"])
        prev_hash = str(row["prev_hash"] or "")
        if prev_hash != prev:
            return False, rid, "prev_hash_mismatch"
        calc = event_hash(
            prev_hash,
            str(row["ts"] or ""),
            str(row["event_type"] or ""),
            str(row["entity_type"] or ""),
            int(row["entity_id"] or 0),
            str(row["payload_json"] or ""),
        )
        stored = str(row["hash"] or "")
        if calc != stored:
            return False, rid, "hash_mismatch"
        prev = stored
    return True, None, None


def event_get_history(entity_type: str, entity_id: int, limit: int = 50) -> list[dict]:
    ensure_eventlog_schema()
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT * FROM events
            WHERE entity_type=? AND entity_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            ((entity_type or "").strip(), int(entity_id), max(1, min(int(limit), 500))),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.get("payload_json") or "{}")
            except Exception:
                item["payload"] = {}
            out.append(item)
        return out
    finally:
        con.close()
