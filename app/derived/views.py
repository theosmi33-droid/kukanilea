from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict

from flask import current_app, has_app_context

from app.config import Config


def _core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _connect() -> sqlite3.Connection:
    db = _core_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def ensure_derived_schema() -> None:
    con = _connect()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS derived_active_timers(
              user_id INTEGER PRIMARY KEY,
              task_id INTEGER NOT NULL,
              start_time TEXT NOT NULL,
              last_event_id INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS derived_budget_progress(
              project_id INTEGER PRIMARY KEY,
              total_hours REAL,
              total_cost REAL,
              budget_hours REAL,
              budget_cost REAL,
              hours_percent REAL,
              cost_percent REAL,
              last_event_id INTEGER
            )
            """
        )
        con.commit()
    finally:
        con.close()


def _payload(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        obj = json.loads(str(row["payload_json"] or "{}"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def rebuild_active_timers() -> int:
    ensure_derived_schema()
    con = _connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM derived_active_timers")
        rows = con.execute(
            """
            SELECT id, event_type, payload_json
            FROM events
            WHERE event_type IN ('timer_started', 'timer_stopped')
            ORDER BY id ASC
            """
        ).fetchall()
        active: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            evt = str(row["event_type"] or "")
            payload = _payload(row)
            uid = int(payload.get("user_id") or 0)
            if uid <= 0:
                continue
            if evt == "timer_started":
                active[uid] = {
                    "task_id": int(payload.get("task_id") or 0),
                    "start_time": str(
                        payload.get("start_time") or payload.get("start_at") or ""
                    ),
                    "last_event_id": int(row["id"]),
                }
            elif evt == "timer_stopped":
                active.pop(uid, None)

        for uid, state in active.items():
            if int(state.get("task_id") or 0) <= 0:
                continue
            if not str(state.get("start_time") or ""):
                continue
            con.execute(
                """
                INSERT INTO derived_active_timers(user_id, task_id, start_time, last_event_id)
                VALUES (?,?,?,?)
                """,
                (
                    uid,
                    int(state["task_id"]),
                    str(state["start_time"]),
                    int(state["last_event_id"]),
                ),
            )

        con.commit()
        return len(active)
    finally:
        con.close()


def rebuild_budget_progress() -> int:
    ensure_derived_schema()
    con = _connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM derived_budget_progress")

        max_evt = con.execute("SELECT COALESCE(MAX(id), 0) AS m FROM events").fetchone()
        last_event_id = int((max_evt["m"] if max_evt else 0) or 0)

        rows = con.execute(
            """
            SELECT
              p.id AS project_id,
              COALESCE(SUM(COALESCE(te.duration_seconds, te.duration, 0)), 0) / 3600.0 AS total_hours,
              COALESCE(p.budget_hours, 0) AS budget_hours,
              COALESCE(p.budget_cost, 0) AS budget_cost
            FROM time_projects p
            LEFT JOIN time_entries te ON te.project_id = p.id AND te.tenant_id = p.tenant_id
            GROUP BY p.id, p.budget_hours, p.budget_cost
            ORDER BY p.id
            """
        ).fetchall()

        count = 0
        for row in rows:
            total_hours = float(row["total_hours"] or 0.0)
            budget_hours = float(row["budget_hours"] or 0.0)
            budget_cost = float(row["budget_cost"] or 0.0)
            hours_percent = (
                (total_hours / budget_hours * 100.0) if budget_hours > 0 else 0.0
            )
            total_cost = (
                (total_hours / budget_hours * budget_cost) if budget_hours > 0 else 0.0
            )
            cost_percent = (
                (total_cost / budget_cost * 100.0) if budget_cost > 0 else 0.0
            )

            con.execute(
                """
                INSERT INTO derived_budget_progress(
                  project_id, total_hours, total_cost, budget_hours, budget_cost,
                  hours_percent, cost_percent, last_event_id
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    int(row["project_id"]),
                    total_hours,
                    total_cost,
                    budget_hours,
                    budget_cost,
                    hours_percent,
                    cost_percent,
                    last_event_id,
                ),
            )
            count += 1

        con.commit()
        return count
    finally:
        con.close()


def rebuild_all() -> Dict[str, int]:
    active = rebuild_active_timers()
    budgets = rebuild_budget_progress()
    return {"active_timers": active, "budget_rows": budgets}
