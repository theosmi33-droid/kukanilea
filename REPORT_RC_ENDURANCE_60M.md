# REPORT_RC_ENDURANCE_60M

Date: 2026-02-21  
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`  
Branch: `codex/bench-and-stability`

## Scope
- Reproducible endurance runner for RC evidence.
- Repeats E2E hardening smoke checks and periodic latency snapshots.
- Exports machine-readable artifacts for audit and re-check.

## Runner
- Script: `scripts/run_endurance_60m.py`
- Default mode: `--duration-minutes 60`
- Sanity mode: `--sanity` (5-minute quick run)

## Commands
```bash
# 5-minute sanity run
python scripts/run_endurance_60m.py --sanity

# 60-minute RC run
python scripts/run_endurance_60m.py --duration-minutes 60
```

## Pass/Fail Criteria
- PASS:
  - Duration completes.
  - No E2E failures (`e2e_fail_runs = 0`).
  - No latency error runs (`latency_ai_error_runs = 0`, `latency_search_error_runs = 0`).
- FAIL:
  - Any E2E failure run.
  - Any latency run with non-zero API error counts.

## Artifacts
- `output/endurance/summary.json`
- `output/endurance/latency.csv`
- `output/endurance/e2e_failures/`

## Sanity Run Evidence (5-minute)

Command:
```bash
python scripts/run_endurance_60m.py \
  --sanity \
  --e2e-interval-seconds 90 \
  --latency-interval-seconds 180 \
  --latency-requests 6
```

Result:
- Started: `2026-02-21T22:07:11Z`
- Ended: `2026-02-21T22:12:11Z`
- Duration: `300.70s`
- E2E iterations: `4/4 passed`, `0 failed`
- Latency snapshots: `2`
- AI errors: `0`
- Search errors: `0`
- Sanity verdict: `PASS`

Latency snapshots:

| Snapshot | AI p50 (ms) | AI p95 (ms) | Search p50 (ms) | Search p95 (ms) |
|---|---:|---:|---:|---:|
| 1 | 1.095 | 1.406 | 5.303 | 9.355 |
| 2 | 1.143 | 1.398 | 4.614 | 7.780 |

## 60-minute RC Evidence
- Runner is ready.
- Execute:
  ```bash
  python scripts/run_endurance_60m.py --duration-minutes 60
  ```
- RC PASS requires:
  - `e2e_fail_runs = 0`
  - `latency_ai_error_runs = 0`
  - `latency_search_error_runs = 0`
  - no P1 failures documented in `failures[]`
