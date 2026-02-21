# REPORT_AI_AVAILABILITY

Date: 2026-02-21
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`

## Scope
- Primary/fallback provider health
- Latency and failure behavior under provider-down scenarios
- Pass/Fail against AI availability gate

## Pre-risk git status evidence
Command:
```bash
git status --porcelain=v1
```
Output:
```text
<clean>
```

## Provider health evidence
From `/tmp/kuka_ai_provider_doctor.json`:
- Provider order: `ollama -> vllm -> lmstudio -> groq`
- Health snapshot:
  - `ollama`: healthy
  - `vllm`: unhealthy
  - `lmstudio`: unhealthy
  - `groq`: unhealthy (api key not configured)

## Bench evidence
### Mock mode baseline
`/tmp/kuka_bench_llm_mock.json`
- 80 requests, 80 ok, 0 error
- p95: 2.027ms

### Local real AI
`/tmp/kuka_bench_llm_local.json`
- 6 requests, 6 ok, 0 error
- avg: 11482.38ms
- p95: 14612.92ms

### Provider-down scenario
`/tmp/kuka_bench_llm_down.json`
- 6 requests, 6 ok, 0 error
- avg: 3.616ms
- p95: 6.708ms

### Additional real sample
`/tmp/kuka_bench_llm_real5.json`
- 5 requests, 5 ok, 0 error
- avg: 12118.068ms
- p95: 14885.448ms

## Pass/Fail vs Release Gates (AI availability)
| Gate target | Status | Reason | Evidence |
|---|---|---|---|
| Beta: primary + fallback function | PASS | requests remain successful in local and down scenarios; no hard failure in benchmark harness | `kuka_bench_llm_local/down/mock` |
| RC: provider outage fallback without UI block | PARTIAL PASS | backend fallback behavior is healthy; dedicated UI-flow outage test with authenticated session still needed | benchmark JSON + pending UI scenario |
| Prod: offline-first + recovery runbook | PARTIAL FAIL | offline-first partially met (local ollama healthy), but full recovery runbook evidence for all provider permutations not completed | provider doctor + this report |

## How to verify
1. Start app with local primary provider.
2. Run authenticated UI chat flow and record p50/p95.
3. Stop primary provider; verify fallback response path and non-blocking UI behavior.
4. Restore provider; validate recovery without restart.
5. Attach logs + request IDs + benchmark artifact paths.

## Findings
1. Local AI works but latency is high (~11–15s p95) on this hardware/profile.
2. Fallback behavior appears robust at API benchmark level.
3. Cloud fallback is currently non-operational in this environment (no API key / unavailable endpoints).
