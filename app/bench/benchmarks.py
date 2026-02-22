from __future__ import annotations

import random
import sqlite3
import statistics
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from app.bench.core import recompute_task_duration_benchmarks
from app.eventlog.core import event_append, event_verify_chain


def _events_schema(con: sqlite3.Connection) -> None:
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


def bench_event_verify_chain_synth(n_events: int = 2000) -> float:
    """Benchmark chain verification with deterministic synthetic events."""
    with tempfile.TemporaryDirectory(prefix="kukanilea_bench_events_") as tmp:
        db_path = Path(tmp) / "events.sqlite3"
        con = sqlite3.connect(str(db_path), timeout=30)
        con.row_factory = sqlite3.Row
        try:
            _events_schema(con)
            for idx in range(1, n_events + 1):
                event_append(
                    event_type="bench_event",
                    entity_type="synthetic",
                    entity_id=idx,
                    payload={"idx": idx, "seed": 0},
                    con=con,
                )
            con.commit()
            start = time.perf_counter()
            ok, _, _ = event_verify_chain(con=con)
            elapsed = time.perf_counter() - start
            if not ok:
                raise RuntimeError("event chain verify failed")
            return elapsed
        finally:
            con.close()


def _bench_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY,
            project_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS time_entries(
            id INTEGER PRIMARY KEY,
            task_id INTEGER,
            duration INTEGER
        );
        CREATE TABLE IF NOT EXISTS benchmarks(
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
        );
        CREATE TABLE IF NOT EXISTS events(
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


def bench_recompute_benchmarks_synth(
    n_entries: int = 5000,
    n_projects: int = 20,
    n_tasks: int = 200,
) -> float:
    """Benchmark recompute over deterministic synthetic durations."""
    rng = random.Random(0)
    with tempfile.TemporaryDirectory(prefix="kukanilea_bench_recompute_") as tmp:
        db_path = Path(tmp) / "bench.sqlite3"
        con = sqlite3.connect(str(db_path), timeout=30)
        con.row_factory = sqlite3.Row
        try:
            _bench_schema(con)
            tasks = [
                (task_id, (task_id % n_projects) + 1)
                for task_id in range(1, n_tasks + 1)
            ]
            con.executemany("INSERT INTO tasks(id, project_id) VALUES (?,?)", tasks)

            entries = []
            for entry_id in range(1, n_entries + 1):
                task_id = (entry_id % n_tasks) + 1
                duration = rng.randint(30, 14_400)
                entries.append((entry_id, task_id, duration))
            con.executemany(
                "INSERT INTO time_entries(id, task_id, duration) VALUES (?,?,?)",
                entries,
            )
            con.execute(
                "INSERT INTO events(id, ts, event_type, entity_type, entity_id, payload_json, prev_hash, hash) VALUES (1,'2026-01-01T00:00:00+00:00','seed','bench',1,'{}','0','h')"
            )
            con.commit()

            start = time.perf_counter()
            summary = recompute_task_duration_benchmarks(con=con)
            elapsed = time.perf_counter() - start
            if int(summary.get("inserted_rows", 0)) <= 0:
                raise RuntimeError("benchmark recompute inserted no rows")
            return elapsed
        finally:
            con.close()


def run_many(fn: Callable[[], float], runs: int, warmup: int) -> float:
    """Run benchmark function multiple times and return median measured time."""
    runs = max(1, int(runs))
    warmup = max(0, int(warmup))
    for _ in range(warmup):
        fn()
    samples = [fn() for _ in range(runs)]
    return float(statistics.median(samples))


def run_benchmark_suite(
    runs: int = 5,
    warmup: int = 1,
    time_budget_secs: float = 20.0,
) -> dict[str, float]:
    """Run robust synth benchmarks and return median timings."""
    budget = float(time_budget_secs)
    started = time.perf_counter()
    out = {
        "event_verify_chain_synth_2000": run_many(
            lambda: bench_event_verify_chain_synth(2000), runs=runs, warmup=warmup
        ),
        "recompute_task_duration_synth": run_many(
            bench_recompute_benchmarks_synth, runs=runs, warmup=warmup
        ),
    }
    elapsed = time.perf_counter() - started
    if elapsed > budget:
        raise RuntimeError("benchmark time budget exceeded")
    return out


def run_all() -> dict[str, float]:
    """Backward-compatible alias to the robust suite."""
    return run_benchmark_suite()
