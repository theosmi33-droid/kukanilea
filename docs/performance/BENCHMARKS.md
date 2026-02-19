# Phase 2 Benchmarks

## Method
Benchmarks are executed with local scripts:

```bash
python scripts/bench_ocr.py --docs 100
python scripts/bench_llm.py --requests 50
python scripts/bench_workflows.py --events 100
```

## Baseline (2026-02-19, local dev machine)

| Area | Input | P50 ms | P95 ms | P99 ms | Error rate | Notes |
|------|-------|--------|--------|--------|------------|-------|
| OCR (synthetic redaction path) | 20 docs | 0.010 | 0.012 | 0.028 | 0% | `python scripts/bench_ocr.py --docs 20` |
| LLM API (mocked orchestrator) | 10 requests | 0.229 | 0.465 | 0.465 | 0% | `python scripts/bench_llm.py --requests 10` |
| Workflow simulation | 20 events | 1.699 | 2.183 | 2.196 | 0% | `python scripts/bench_workflows.py --events 20` |

## Interpretation
- Focus on trend over absolute numbers.
- Compare with prior run before beta cut.
- Track tail latency (P95/P99), not only average.
