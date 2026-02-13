from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Config


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect_core_db() -> sqlite3.Connection:
    db_path = Path(Config.CORE_DB)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def _column_exists(con: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return False
    return any(str(r[1]) == column for r in rows)


def _ensure_benchmarks_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            metric TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id INTEGER,
            n INTEGER NOT NULL,
            p50 REAL NOT NULL,
            p75 REAL NOT NULL,
            p90 REAL NOT NULL,
            min REAL,
            max REAL,
            last_event_id INTEGER
        )
        """
    )


def compute_percentiles(values: list[float]) -> dict[str, float | int]:
    """Compute nearest-rank percentiles for a non-empty list."""
    if not values:
        raise ValueError("values_required")
    ordered = sorted(float(v) for v in values)
    n = len(ordered)

    def nearest_rank(q: float) -> float:
        rank = max(1, math.ceil(q * n))
        idx = min(n, rank) - 1
        return float(ordered[idx])

    return {
        "n": n,
        "p50": nearest_rank(0.50),
        "p75": nearest_rank(0.75),
        "p90": nearest_rank(0.90),
        "min": float(ordered[0]),
        "max": float(ordered[-1]),
    }


def recompute_task_duration_benchmarks(
    con: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Append benchmark rows for global and project task durations."""
    owns_connection = con is None
    db = con or _connect_core_db()
    inserted_rows = 0
    groups_global = 0
    groups_project = 0
    total_samples = 0

    try:
        _ensure_benchmarks_table(db)

        durations: list[float] = []
        if _table_exists(db, "time_entries") and _column_exists(
            db, "time_entries", "duration"
        ):
            rows = db.execute(
                "SELECT duration FROM time_entries WHERE duration IS NOT NULL AND duration > 0"
            ).fetchall()
            durations = [float(r[0]) for r in rows]

        project_groups: dict[int, list[float]] = {}
        if (
            _table_exists(db, "time_entries")
            and _table_exists(db, "tasks")
            and _column_exists(db, "time_entries", "task_id")
            and _column_exists(db, "time_entries", "duration")
            and _column_exists(db, "tasks", "project_id")
        ):
            rows = db.execute(
                """
                SELECT te.duration AS duration, t.project_id AS project_id
                FROM time_entries te
                JOIN tasks t ON t.id = te.task_id
                WHERE te.duration IS NOT NULL
                  AND te.duration > 0
                  AND t.project_id IS NOT NULL
                """
            ).fetchall()
            for row in rows:
                project_id = int(row["project_id"])
                project_groups.setdefault(project_id, []).append(float(row["duration"]))

        last_event_id: int | None = None
        if _table_exists(db, "events"):
            row = db.execute("SELECT MAX(id) AS max_id FROM events").fetchone()
            if row and row["max_id"] is not None:
                last_event_id = int(row["max_id"])

        ts = _utcnow_iso()

        if durations:
            stats = compute_percentiles(durations)
            db.execute(
                """
                INSERT INTO benchmarks(
                    ts, metric, scope_type, scope_id, n, p50, p75, p90, min, max, last_event_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ts,
                    "task_duration_seconds",
                    "global",
                    None,
                    int(stats["n"]),
                    float(stats["p50"]),
                    float(stats["p75"]),
                    float(stats["p90"]),
                    float(stats["min"]),
                    float(stats["max"]),
                    last_event_id,
                ),
            )
            inserted_rows += 1
            groups_global = 1
            total_samples = len(durations)

        for project_id in sorted(project_groups):
            values = project_groups[project_id]
            if not values:
                continue
            stats = compute_percentiles(values)
            db.execute(
                """
                INSERT INTO benchmarks(
                    ts, metric, scope_type, scope_id, n, p50, p75, p90, min, max, last_event_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ts,
                    "task_duration_seconds",
                    "project",
                    int(project_id),
                    int(stats["n"]),
                    float(stats["p50"]),
                    float(stats["p75"]),
                    float(stats["p90"]),
                    float(stats["min"]),
                    float(stats["max"]),
                    last_event_id,
                ),
            )
            inserted_rows += 1
            groups_project += 1

        if owns_connection:
            db.commit()

        return {
            "inserted_rows": inserted_rows,
            "groups_global": groups_global,
            "groups_project": groups_project,
            "total_samples": total_samples,
            "last_event_id": last_event_id,
        }
    finally:
        if owns_connection:
            db.close()


def benchmarks_latest(
    con: sqlite3.Connection,
    metric: str,
    scope_type: str,
    scope_id: int | None,
) -> dict[str, Any] | None:
    """Return the newest benchmark row for metric + scope."""
    if scope_id is None:
        row = con.execute(
            """
            SELECT * FROM benchmarks
            WHERE metric=? AND scope_type=? AND scope_id IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (metric, scope_type),
        ).fetchone()
    else:
        row = con.execute(
            """
            SELECT * FROM benchmarks
            WHERE metric=? AND scope_type=? AND scope_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (metric, scope_type, int(scope_id)),
        ).fetchone()
    return dict(row) if row else None
