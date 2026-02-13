from __future__ import annotations

import sqlite3
from pathlib import Path

from app.bench.core import compute_percentiles, recompute_task_duration_benchmarks


def test_percentiles_nearest_rank_small() -> None:
    one = compute_percentiles([5])
    assert one["n"] == 1
    assert one["p50"] == 5.0
    assert one["p75"] == 5.0
    assert one["p90"] == 5.0

    three = compute_percentiles([1, 5, 9])
    assert three["n"] == 3
    assert three["p50"] == 5.0
    assert three["p75"] == 9.0
    assert three["p90"] == 9.0

    ten = compute_percentiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert ten["n"] == 10
    assert ten["p50"] == 5.0
    assert ten["p75"] == 8.0
    assert ten["p90"] == 9.0


def test_recompute_inserts_rows_global_and_project(tmp_path: Path) -> None:
    db = tmp_path / "bench.sqlite3"
    con = sqlite3.connect(str(db), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(
            """
            CREATE TABLE tasks(
                id INTEGER PRIMARY KEY,
                project_id INTEGER
            );
            CREATE TABLE time_entries(
                id INTEGER PRIMARY KEY,
                task_id INTEGER,
                duration INTEGER
            );
            CREATE TABLE events(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                event_type TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                payload_json TEXT,
                prev_hash TEXT,
                hash TEXT
            );
            """
        )
        con.executemany(
            "INSERT INTO tasks(id, project_id) VALUES (?,?)",
            [(1, 101), (2, 102), (3, None)],
        )
        con.executemany(
            "INSERT INTO time_entries(id, task_id, duration) VALUES (?,?,?)",
            [
                (1, 1, 60),
                (2, 1, 120),
                (3, 2, 30),
                (4, 3, 15),
                (5, 2, None),
            ],
        )
        con.executemany(
            "INSERT INTO events(id, ts) VALUES (?,?)",
            [(10, "2026-01-01T00:00:00+00:00"), (11, "2026-01-01T00:00:01+00:00")],
        )

        summary = recompute_task_duration_benchmarks(con=con)

        assert summary["inserted_rows"] == 3
        assert summary["groups_global"] == 1
        assert summary["groups_project"] == 2
        assert summary["total_samples"] == 4
        assert summary["last_event_id"] == 11

        rows = con.execute(
            "SELECT * FROM benchmarks ORDER BY scope_type, scope_id"
        ).fetchall()
        assert len(rows) == 3

        global_row = con.execute(
            "SELECT * FROM benchmarks WHERE scope_type='global' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert global_row is not None
        assert int(global_row["n"]) == 4
        assert float(global_row["min"]) == 15.0
        assert float(global_row["max"]) == 120.0
        assert float(global_row["p50"]) == 30.0
        assert float(global_row["p75"]) == 60.0
        assert float(global_row["p90"]) == 120.0

        p101 = con.execute(
            "SELECT * FROM benchmarks WHERE scope_type='project' AND scope_id=101 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert p101 is not None
        assert int(p101["n"]) == 2
        assert float(p101["min"]) == 60.0
        assert float(p101["max"]) == 120.0

        p102 = con.execute(
            "SELECT * FROM benchmarks WHERE scope_type='project' AND scope_id=102 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert p102 is not None
        assert int(p102["n"]) == 1
        assert float(p102["p50"]) == 30.0
    finally:
        con.close()
