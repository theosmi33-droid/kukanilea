# Launch Evidence Gate Automation Report

- Timestamp: 2026-03-06T22:00:24+00:00
- Decision: **FAIL**
- Exit-Code: 3
- Repo: unknown

## Gate Matrix

| Gate | Status | Note |
|---|---|---|
| Repo/CI | PASS | git HEAD resolvable |
| MIN_SCOPE | PASS | files=7 loc=245 |
| Health | WARN | skipped by flag |
| Zero-CDN | PASS | guardrails passed |
| White-mode | PASS | no dark mode signatures |
| License | FAIL | status=LOCK:MISSING |
| Backup | FAIL | backup/restore drill execution failed |
| AI | PASS | AI operating contract present |
| MIN_TESTS | PASS | tests/ops test-count=49 |
| CI_GATE | PASS | pytest tests/ops passed |
| MIA_GATE7_SMOKE | PASS | gate7 smoke evidence generated in /workspace/kukanilea/evidence/operations/gate7_latest |
| MIA_GATE7_ARTIFACTS | PASS | gate7 artifacts contain required evidence matrix |
| MIA_UNCONTROLLED_WRITES | PASS | writes limited to controlled code/test paths |
| Evidence | FAIL | evidence path mismatch (required docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_20260305.md) |

## Totals

- PASS: 10
- WARN: 1
- FAIL: 3
