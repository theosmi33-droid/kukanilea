# REPORT_HARDENING_PERF

Date: 2026-02-21  
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`  
Branch: `codex/bench-and-stability`

## Scope
- Reproducible latency harness for:
  - `POST /api/ai/chat` (mocked AI path by default)
  - `GET /api/knowledge/search` (FTS search baseline)
- p50/p95 collection with `time.perf_counter()`
- Threshold profiles (`dev` warn-first, `ci` fail-first)

## Pre-run git status
Command:
```bash
git status --porcelain=v1
```

Output:
```text
 M app/bench/hardening_latency.py
?? docs/performance/hardening_latency_thresholds.json
?? output/
?? scripts/bench_hardening_latency.py
?? tests/test_hardening_latency_bench.py
```

## Commands
```bash
python scripts/bench_hardening_latency.py \
  --requests 20 \
  --profile dev \
  --threshold-file docs/performance/hardening_latency_thresholds.json \
  --json-out output/perf/hardening-latency-dev.json

python scripts/bench_hardening_latency.py \
  --requests 20 \
  --profile ci \
  --threshold-file docs/performance/hardening_latency_thresholds.json \
  --json-out output/perf/hardening-latency-ci.json
```

## Result Summary

| Metric | Dev (p95 ms) | CI (p95 ms) | Threshold (dev/ci) | Status |
|---|---:|---:|---:|---|
| AI chat | 1.265 | 1.180 | 2000 / 2200 | PASS |
| Knowledge search | 5.851 | 5.933 | 800 / 900 | PASS |

## Threshold Policy
- `dev` profile: over-limit metrics generate warnings (`severity=warn`).
- `ci` profile: over-limit metrics fail the benchmark command (`severity=fail`, non-zero exit).
- Threshold config source: `docs/performance/hardening_latency_thresholds.json`

## Evidence Artifacts
- `output/perf/hardening-latency-dev.json`
- `output/perf/hardening-latency-ci.json`
- `scripts/bench_hardening_latency.py`
- `app/bench/hardening_latency.py`
- `tests/test_hardening_latency_bench.py`
