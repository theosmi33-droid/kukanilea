from __future__ import annotations

import json

from app.bench.core import recompute_task_duration_benchmarks


def main() -> int:
    summary = recompute_task_duration_benchmarks()
    print(json.dumps(summary, sort_keys=True))
    print(
        "bench recompute done: inserted_rows="
        f"{summary.get('inserted_rows', 0)} "
        f"samples={summary.get('total_samples', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
