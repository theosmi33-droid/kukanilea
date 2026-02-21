# REPORT_BENCH_STABILITY

Date: 2026-02-21
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`

## Scope
- Baseline quality gates
- UI stability benchmark
- Workflow throughput benchmark
- Pass/Fail against `docs/RELEASE_GATES.md` for Performance/Stability

## Pre-risk git status evidence
Command:
```bash
git status --porcelain=v1
```
Output:
```text
<clean>
```

## Environment
- OS: macOS 26.3 (Darwin 25.3.0 arm64)
- Python: 3.12.0
- Node: not installed
- Ollama: 0.16.3

## Baseline gates
- `python -m compileall -q .` + `ruff check .` + `ruff format . --check`: PASS
  - Evidence: `/tmp/kuka_quality_gate_basics.log`
- `pytest -q`: PASS (`539 passed, 6 skipped, 29 warnings`)
  - Evidence: `/tmp/kuka_pytest_full_bench.log`
- `python -m app.devtools.triage --ci --fail-on-warnings ...`: FAIL (`chat latency too high`)
  - Evidence: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/triage_report.json`, `/tmp/kuka_triage_bench.log`

## Benchmark results

### UI stability load (5 min, validated run)
Command (server + benchmark): `scripts/bench_ui_stability.py --duration 300 --html-workers 1 --api-workers 1`

Metrics (from `/tmp/kuka_bench_ui_5m.json`):
- Duration: 300s
- HTML total: 22,975
- API total: 44,729
- API 4xx: 44,729 (auth-gated API calls under load harness)
- Latency p50: 10.62ms
- Latency p95: 14.05ms
- Latency max: 89.27ms
- `failures_sample`: empty

### UI stability load (15 min artifact)
`/tmp/kuka_bench_ui_15m.json` is INVALID for acceptance (server not reachable at start; login connection refused).

### Workflow benchmark
From `/tmp/kuka_bench_workflows_200.json`:
- Events: 200
- OK: 200
- Errors: 0
- p50: 1.703ms
- p95: 2.592ms

## Pass/Fail vs Release Gates (Performance/Stability)
| Gate target | Status | Reason | Evidence |
|---|---|---|---|
| Beta: 15–20 min smoke without blocker | FAIL | Validated run available only for 5 min; 15-min artifact invalid due startup connection refusal | `/tmp/kuka_bench_ui_5m.json`, `/tmp/kuka_bench_ui_15m.json` |
| RC: 60 min Dauerlast without P1 | FAIL | 60-min validated benchmark not executed in this run | n/a |
| Prod: reproducible load test + thresholds defined | FAIL | Thresholds and reproducibility protocol not finalized | this report |

## Repro / How to verify
1. Start local app server in benchmark mode.
2. Run `scripts/bench_ui_stability.py` for 20 min with fixed workers.
3. Repeat with 60 min; archive JSON artifacts.
4. Re-run `python -m app.devtools.triage --ci --fail-on-warnings ...`.
5. Compare p50/p95 and error rates against agreed thresholds.

## Findings
1. `triage` currently fails due high chat latency (P1 reliability).
2. Need a valid 20-min + 60-min run to satisfy RC/Prod gates.
3. API 4xx under harness indicates benchmark script is not using authenticated API calls for those routes; metrics are still useful for responsiveness, not business-flow correctness.
