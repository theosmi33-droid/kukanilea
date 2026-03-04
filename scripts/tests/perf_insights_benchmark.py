from __future__ import annotations

import json
import sqlite3
import statistics
import time
from pathlib import Path

ITERATIONS = 200
TENANT = "KUKANILEA"
OUT = Path("docs/status/perf_insights_benchmark_latest.json")


def _setup_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            tenant_id TEXT,
            created_at TEXT,
            response_due TEXT,
            status TEXT,
            priority TEXT,
            assigned_to TEXT
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            tenant TEXT,
            status TEXT
        );
        """
    )

    lead_rows = []
    for i in range(1, 6001):
        created = "datetime('now','-12 hours')" if i % 3 == 0 else "datetime('now','-2 day')"
        due = "datetime('now','-10 minutes')" if i % 5 == 0 else "datetime('now','+1 day')"
        status = "screening" if i % 4 == 0 else "open"
        priority = "high" if i % 7 == 0 else "normal"
        assignee = "''" if i % 11 == 0 else "'owner'"
        lead_rows.append(
            f"('{TENANT}', {created}, {due}, '{status}', '{priority}', {assignee})"
        )

    con.executescript(
        "INSERT INTO leads(tenant_id, created_at, response_due, status, priority, assigned_to) VALUES\n"
        + ",\n".join(lead_rows)
        + ";\n"
    )

    task_rows = [f"('{TENANT}','OPEN')" if i % 2 == 0 else f"('{TENANT}','DONE')" for i in range(1, 2001)]
    con.executescript(
        "INSERT INTO tasks(tenant, status) VALUES\n" + ",\n".join(task_rows) + ";\n"
    )
    return con


def _legacy_counts(con: sqlite3.Connection) -> dict[str, int]:
    row1 = con.execute(
        "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND datetime(created_at) >= datetime('now','-1 day')",
        (TENANT,),
    ).fetchone()
    row2 = con.execute(
        "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND response_due IS NOT NULL AND datetime(response_due) < datetime('now')",
        (TENANT,),
    ).fetchone()
    row3 = con.execute(
        "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND status='screening'",
        (TENANT,),
    ).fetchone()
    row4 = con.execute(
        "SELECT COUNT(*) AS c FROM leads WHERE tenant_id=? AND priority='high' AND (assigned_to IS NULL OR assigned_to='')",
        (TENANT,),
    ).fetchone()
    row5 = con.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE tenant=? AND status='OPEN'",
        (TENANT,),
    ).fetchone()
    return {
        "leads_new_24h_count": int(row1["c"]),
        "leads_overdue_count": int(row2["c"]),
        "leads_screening_count": int(row3["c"]),
        "leads_unassigned_high_priority_count": int(row4["c"]),
        "tasks_open_count": int(row5["c"]),
    }


def _optimized_counts(con: sqlite3.Connection) -> dict[str, int]:
    aggregate = con.execute(
        """
        SELECT
          SUM(CASE WHEN datetime(created_at) >= datetime('now','-1 day') THEN 1 ELSE 0 END) AS leads_new_24h_count,
          SUM(CASE WHEN response_due IS NOT NULL AND datetime(response_due) < datetime('now') THEN 1 ELSE 0 END) AS leads_overdue_count,
          SUM(CASE WHEN status='screening' THEN 1 ELSE 0 END) AS leads_screening_count,
          SUM(CASE WHEN priority='high' AND (assigned_to IS NULL OR assigned_to='') THEN 1 ELSE 0 END) AS leads_unassigned_high_priority_count
        FROM leads
        WHERE tenant_id=?
        """,
        (TENANT,),
    ).fetchone()
    tasks = con.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE tenant=? AND status='OPEN'",
        (TENANT,),
    ).fetchone()
    return {
        "leads_new_24h_count": int(aggregate["leads_new_24h_count"] or 0),
        "leads_overdue_count": int(aggregate["leads_overdue_count"] or 0),
        "leads_screening_count": int(aggregate["leads_screening_count"] or 0),
        "leads_unassigned_high_priority_count": int(
            aggregate["leads_unassigned_high_priority_count"] or 0
        ),
        "tasks_open_count": int(tasks["c"]),
    }


def _measure(fn, con: sqlite3.Connection) -> tuple[dict[str, int], list[float]]:
    latencies = []
    data = {}
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        data = fn(con)
        latencies.append((time.perf_counter() - start) * 1000)
    return data, latencies


def main() -> None:
    con = _setup_db()
    legacy_result, legacy_lat = _measure(_legacy_counts, con)
    optimized_result, optimized_lat = _measure(_optimized_counts, con)

    if legacy_result != optimized_result:
        raise SystemExit(f"Result mismatch: {legacy_result} vs {optimized_result}")

    report = {
        "iterations": ITERATIONS,
        "legacy": {
            "mean_ms": round(statistics.mean(legacy_lat), 3),
            "p95_ms": round(statistics.quantiles(legacy_lat, n=20)[18], 3),
        },
        "optimized": {
            "mean_ms": round(statistics.mean(optimized_lat), 3),
            "p95_ms": round(statistics.quantiles(optimized_lat, n=20)[18], 3),
        },
        "delta_mean_percent": round(
            ((statistics.mean(legacy_lat) - statistics.mean(optimized_lat)) / statistics.mean(legacy_lat)) * 100,
            2,
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
